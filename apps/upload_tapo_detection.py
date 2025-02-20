from pytapo import Tapo
from pytapo.media_stream.downloader import Downloader
import sys
import os
import stat
import shutil
from datetime import datetime
from dataclasses import dataclass
import hassapi as hass

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
        self.tapo = 0 # initialize, we'll get this as needed
        self.date = "" # initialize, we'll set this when we want to upload
        # optional
        self.window_size = 100 #os.environ.get("WINDOW_SIZE")  # set to prefferred window size, affects download speed and stability, recommended: 50, default is 200
        self.log("Initialized!")
        #TODO: how to have HA call it upon a certain action
        self.create_task(self.execute())

    async def execute(self):
        #date = datetime.now().strftime("%Y%m%d") # date to download recordings for in format YYYYMMDD
        self.date = "20250217"#TODO this is just test, uncomment above
        self.log("Connecting to camera...")
        self.tapo = Tapo(self.host, "admin", self.passwordCloud, self.passwordCloud)

        #loop = asyncio.get_event_loop()
        timeTaken = datetime.now()
        DownloadedFile = await self.DownloadAsync()

        if not DownloadedFile.isValid:
            self.log("Downloaded file was invalid!")
            sys.exit()

        self.log("Download time taken: " + str(datetime.now() - timeTaken))
        newFilePath = "{}{}".format(self.destination, DownloadedFile.fileName)
        shutil.move("{}{}".format(self.outputDir, DownloadedFile.fileName), newFilePath)
        os.chmod(newFilePath, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
        self.log("Finished!")

    def GetFileInfo(self):
        self.log("Getting recordings...")
        recordings = self.tapo.getRecordings(self.date)
        startEnd = (0,0)

        # name all videos of that date, and only download latest
        for recording in recordings:
            for key in recording:
                start = datetime.fromtimestamp(recording[key]["startTime"]).strftime('%Y-%m-%d %H:%M:%S')
                end = datetime.fromtimestamp(recording[key]["endTime"]).strftime('%Y-%m-%d %H:%M:%S')
                self.log("Video file key: " + key + " start " + start + " end: " + end)
                if(startEnd[0] < recording[key]["startTime"]):
                    startEnd = (recording[key]["startTime"], recording[key]["endTime"])
        # Name format: "YYYY.mm.dd_hh.mm.ss-hh.mm.ss.mp4"
        fileName = "{}-{}.mp4".format(datetime.fromtimestamp(startEnd[0]).strftime('%Y.%m.%d_%H.%M.%S'), datetime.fromtimestamp(startEnd[1]).strftime('%H.%M.%S'))
        return self.FileInfo(fileName, startEnd[0], startEnd[1], startEnd[0] != 0 and startEnd[1] != 0)

    async def DownloadAsync(self):
        FileToDownload = self.GetFileInfo()
        if not FileToDownload.isValid:
            return FileToDownload
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
