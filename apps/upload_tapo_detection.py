from pytapo import Tapo
from pytapo.media_stream.downloader import Downloader
import sys
import os
import stat
import shutil
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
from appdaemon.plugins.hass import hassapi as hass

# Taken from https://github.com/JurajNyiri/pytapo/blob/main/experiments/DownloadRecordings.py
# mandatory:
# ffmpeg installed, with bin in path, because e.g. convert.py uses sub process "ffprobe"
# also assumes you've set up rclone already
# py -m venv ./venv
# source ./venv/Scripts/activate
# pip install -r requirements.txt
class UploadTapoDetection(hass.Hass):

    @dataclass
    class FileInfo:
        fileName: str = ""
        startTime: int = 0
        endTime: int = 0
        isValid: bool = False

    def initialize(self):
        self.outputDir = self.args["output"] #os.environ.get("UTAPOD_OUTPUT")# directory path where videos will be saved
        self.host = self.args["host"] #os.environ.get("UTAPOD_HOST")  # change to camera IP
        self.destination = self.args["destination"]
        self.passwordCloud = self.args["password_cloud"] #os.environ.get("UTAPOD_PASSWORD_CLOUD")  # set to your cloud password
        self.entityId = self.args["entity_id"]
        self.tapo = 0 # initialize, we'll get this as needed
        self.date = "" # initialize, we'll set this when we want to upload
        self.startDetectionTime = datetime.now() # detection time to make sure the latest video is gotten.
        # optional
        self.window_size = 100 #os.environ.get("WINDOW_SIZE")  # set to prefferred window size, affects download speed and stability, recommended: 50, default is 200
        #self.listen_event(self.runActionTask, "state_changed")
        self.listen_event(self.runActionTask)
        self.log("Initialized!")

    def runActionTask(self, event_name, data, cb_args):
        '''
        # See all the events and their data from home assistant.
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
            try:
                # perhaps create a scheduled task that would run every couple seconds like 5, but only for like 20 times or something.
                # and modify that if the local file already exists with the latest name, it skips 
                self.create_task(self.execute())
            except:
                self.log("Something went really wrong. Exiting now.")

    async def execute(self):
        self.date = datetime.now().strftime("%Y%m%d") # date to download recordings for in format YYYYMMDD
        #self.date = "20250217"#TODO this is just test, uncomment above
        self.log("Connecting to camera...")
        self.tapo = Tapo(self.host, "admin", self.passwordCloud, self.passwordCloud)
        timeTaken = datetime.now()
        DownloadedFile = await self.DownloadAsync()
        if not DownloadedFile.isValid:
            self.log("Downloaded file was invalid!")
            return
        self.log("Download time taken: " + str(datetime.now() - timeTaken))
        newFilePath = "{}{}".format(self.destination, DownloadedFile.fileName)
        shutil.move("{}{}".format(self.outputDir, DownloadedFile.fileName), newFilePath)
        os.chmod(newFilePath, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
        self.log("Finished!")

    async def GetFileInfo(self):
        self.log("Getting recordings...")
        recordings = self.tapo.getRecordings(self.date)
        startEnd = (0,0)
        #for retry in range(6):
            # name all videos of that date, and only download latest
        # give some time for the video to be made on the device, 5s is not long enough, and 10s is limit, so appdaemon will kill it...
        #time.sleep(5)
        for recording in recordings:
            for key in recording:
                start = datetime.fromtimestamp(recording[key]["startTime"]).strftime('%Y-%m-%d %H:%M:%S')
                end = datetime.fromtimestamp(recording[key]["endTime"]).strftime('%Y-%m-%d %H:%M:%S')
                self.log("Video file key: " + key + " start " + start + " end: " + end)
                # 30s before detection time, as some cctv make the clips several seconds before it.
                #if datetime.fromtimestamp(recording[key]["startTime"]) < self.startDetectionTime - timedelta(seconds=30):
                    # dont even bother with older recordings
                    #continue
                if(startEnd[0] < recording[key]["startTime"]):
                    startEnd = (recording[key]["startTime"], recording[key]["endTime"])
            # if retry == 8:
            #     self.log("Never found a file earlier than {}... exiting.".format(datetime.fromtimestamp(self.startDetectionTime).strftime('%Y-%m-%d %H:%M:%S')))
            #     return self.FileInfo()
            # else:
            #     self.log("No file found earlier than {}, sleep for 1 second".format(datetime.fromtimestamp(self.startDetectionTime).strftime('%Y-%m-%d %H:%M:%S')))
            #     time.sleep(1)
        # Name format: "YYYY.mm.dd_hh.mm.ss-hh.mm.ss.mp4"
        fileName = "{}-{}.mp4".format(datetime.fromtimestamp(startEnd[0]).strftime('%Y.%m.%d_%H.%M.%S'), datetime.fromtimestamp(startEnd[1]).strftime('%H.%M.%S'))
        return self.FileInfo(fileName, startEnd[0], startEnd[1], startEnd[0] != 0 and startEnd[1] != 0)

    async def DownloadAsync(self):
        FileToDownload = await self.GetFileInfo()
        if not FileToDownload.isValid:
            return FileToDownload
        #return#test
        timeCorrection = self.tapo.getTimeCorrection()
        self.log("Download recording {}".format(FileToDownload.fileName))

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
        self.log("\n")
        return FileToDownload
