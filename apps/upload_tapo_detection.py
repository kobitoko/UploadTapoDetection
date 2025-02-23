from pytapo import Tapo
from pytapo.media_stream.downloader import Downloader
import os
import stat
import shutil
from datetime import datetime, timedelta
from dataclasses import dataclass
from appdaemon.plugins.hass import hassapi as hass

# Taken from https://github.com/JurajNyiri/pytapo/blob/main/experiments/DownloadRecordings.py
# needs ffmpeg installed, with bin in path, because e.g. convert.py uses sub process "ffprobe"
class UploadTapoDetection(hass.Hass):

    @dataclass
    class FileInfo:
        fileName: str = ""
        startTime: int = 0
        endTime: int = 0
        isValid: bool = False

    def initialize(self):
        self.outputDir = self.args["output"] # directory path where the video will be downloaded to and saved, include ending "/"
        self.host = self.args["host"] # change to camera IP
        self.destination = self.args["destination"] # directory path where videos will be copied to, after downloading them, include ending "/"
        self.passwordCloud = self.args["password_cloud"] # set to your cloud password
        self.entityId = self.args["entity_id"] # entity id of the sensor from home assistant that will trigger this script
        self.tapo = 0 # initialize pytapo, we'll get this as needed
        self.date = "" # initialize date, we'll set this when we want to download
        self.startDetectionTime = datetime.now() # detection time to make sure a recent video is gotten.
        # optional
        self.window_size = 100 #os.environ.get("WINDOW_SIZE")  # set to prefferred window size, affects download speed and stability, recommended: 50, default is 200
        self.listen_event(self.runActionTask)
        self.log("Initialized!")
        #TEST
        #self.startDetectionTime = datetime(year=2025, month=2, day=17, hour=20, minute=22, second=17) #TEST
        #self.execute() #TEST

    def runActionTask(self, event_name, data, cb_args):
        '''
        # Uncomment to see all the events and their data from home assistant.
        self.log(event_name)
        self.log("data dict:")
        for k,v in data.items():
            self.log("  {}: {}".format(k,v))
        self.log("cb_args dict:")
        for k,v in cb_args.items():
            self.log("  {}: {}".format(k,v))
        self.log("done\n\n")
        '''
        if "entity_id" in data and data["entity_id"] != self.entityId:
            return
        # new state, video doesn't exist yet? should check if OLD state is on and New state is off??
        oldState = "old_state" in data and "state" in data["old_state"] and data["old_state"]["state"]
        newState = "new_state" in data and "state" in data["new_state"] and data["new_state"]["state"]
        if oldState == "off" and newState == "on":
            self.startDetectionTime = datetime.now()
        elif oldState == "on" and newState == "off":
            self.execute()

    def execute(self):
        #self.date = "20250217"# this is just a test
        self.date = datetime.now().strftime("%Y%m%d") # date to download recordings for in format YYYYMMDD
        self.log("Connecting to camera...")
        self.tapo = Tapo(self.host, "admin", self.passwordCloud, self.passwordCloud)
        self.create_task(self.DownloadAsync(), callback=self.MoveDownload)
    
    def MoveDownload(self, kwargs):
        #self.log(str(kwargs)) # what is in kwargs?
        DownloadedFile = kwargs["result"]
        if ("result" not in kwargs) or (not DownloadedFile.isValid):
            self.log("Downloaded file was invalid!")
            return
        newFilePath = "{}{}".format(self.destination, DownloadedFile.fileName)
        if not os.path.isfile("{}{}".format(self.outputDir, DownloadedFile.fileName)):
            self.log("File '{}' not found! Wasn't in the outputDir '{}'. Cannot move it to destination.".format(DownloadedFile.fileName, self.outputDir))
        self.log("Moving downloaded file to {}.".format(self.destination))
        shutil.move("{}{}".format(self.outputDir, DownloadedFile.fileName), newFilePath)
        # permissions might need to change if folder is synced to the cloud with a different software.
        os.chmod(newFilePath, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
        self.log("Finished!\n")

    async def GetFileInfo(self):
        self.log("Getting recordings...")
        recordings = self.tapo.getRecordings(self.date)
        startEnd = (0,0)
        fileName = ""
        # retry up to 30 seconds after trigger ended.
        retries = range(30)
        # 30s before detection time, as some cctv make the clips several seconds before it.
        startTimeVideo = self.startDetectionTime - timedelta(seconds=30)
        for retry in retries:
            # name all videos of that date, and only download latest
            for recording in recordings:
                for key in recording:
                    start = datetime.fromtimestamp(recording[key]["startTime"]).strftime('%Y-%m-%d %H:%M:%S')
                    end = datetime.fromtimestamp(recording[key]["endTime"]).strftime('%Y-%m-%d %H:%M:%S')
                    self.log("Video file key: " + key + " start " + start + " end: " + end)
                    if datetime.fromtimestamp(recording[key]["startTime"]) < startTimeVideo:
                        # dont even bother with older recordings
                        self.log("Skipping: its older than {}".format(startTimeVideo))
                        continue
                    if(startEnd[0] < recording[key]["startTime"]):
                        startTime = recording[key]["startTime"]
                        endTime = recording[key]["endTime"]
                        # Name format: "YYYY.mm.dd_hh.mm.ss-hh.mm.ss.mp4"
                        fileNameCandidate = "{}-{}.mp4".format(datetime.fromtimestamp(startTime).strftime('%Y.%m.%d_%H.%M.%S'), datetime.fromtimestamp(endTime).strftime('%H.%M.%S'))
                        # make sure we don't already have that file
                        if not os.path.isfile("{}{}".format(self.destination, fileNameCandidate)):
                            startEnd = (startTime, endTime)
                            fileName = fileNameCandidate
                        else:
                            self.log("Skipping: Found existing file '{}{}'".format(self.destination, fileName))
            if fileName != "":
                # Found a file to download.
                break
            if retry == retries[-1]:
                self.log("Never found a file later than {} after 30 retries, Exiting.".format(startTimeVideo.strftime('%Y-%m-%d %H:%M:%S')))
                return self.FileInfo()
            else:
                self.log("No file found later than {}, sleep for 1 second. retry:{}".format(startTimeVideo.strftime('%Y-%m-%d %H:%M:%S'), retry))
                await self.sleep(1)
        return self.FileInfo(fileName, startEnd[0], startEnd[1], startEnd[0] != 0 and startEnd[1] != 0)

    async def DownloadAsync(self):
        timeTaken = datetime.now()
        FileToDownload = await self.GetFileInfo()
        if not FileToDownload.isValid:
            return FileToDownload
        timeCorrection = self.tapo.getTimeCorrection()
        self.log("Download recording {}".format(FileToDownload.fileName))
        #return#test

        downloader = Downloader(
            self.tapo,
            FileToDownload.startTime,
            FileToDownload.endTime,
            timeCorrection,
            self.outputDir,
            None,
            False,
            self.window_size,
            FileToDownload.fileName
        )
        async for status in downloader.download():
            statusString = status["currentAction"] + " " + status["fileName"]
            if status["progress"] > 0:
                statusString += (
                    ": "
                    + str(round(status["progress"], 2))
                    + " / "
                    + str(status["total"])
                )
            else:
                statusString += "..."
            self.log(statusString + (" " * 10) + "\r")
        self.log("Download time taken: " + str(datetime.now() - timeTaken))
        return FileToDownload
