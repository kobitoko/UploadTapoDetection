# UploadTapoDetection

On camera motion detection  
Home assist runs a shell script py:  
something like https://github.com/JurajNyiri/pytapo/blob/main/experiments/DownloadRecordings.py  
download clip file to a folder  
This is an appdaemon app with the docker version in mind.  
https://appdaemon.readthedocs.io/en/latest/INSTALL.html#docker-install  

Based on https://github.com/JurajNyiri/pytapo/blob/main/experiments/DownloadRecordings.py  
needs ffmpeg installed (note use Alpine linux packages, as that's what the docker's OS is), with bin in path, because e.g. convert.py uses sub process "ffprobe". system_packages.txt is placed in appdaemon/conf/ folder, which appdaemon will scan and install.  
It also needs the module aiofiles.  

local dev:
`py -m venv ./venv`
`source ./venv/Scripts/activate`
`pip install -r requirements.txt`

HASS plugin does not seem to be loading with numpy > 2 so added <2 in requirements.txt  
https://github.com/hassio-addons/addon-appdaemon/issues/345

appdaemon for IDE when not in appdaemon  
Having trouble with py 3.12, this should work  
`pip install git+https://github.com/AppDaemon/appdaemon.git`

Would want `thread_duration_warning_threshold: 600` be like 10min(600) rather than default 10s or = 00. This will run long, waiting for new video and downloading it, it shouldnt take longer than 10m unless a big long detection happens?  
`production_mode: true` when finished setting it up, save some cpu cycles.

Time/timezone is wrong?  
Set conf/appdaemon.yaml's `time_zone:` entry to desired entry in TZ format:  
https://en.wikipedia.org/wiki/List_of_tz_database_time_zones  
or add the docker command `-v /etc/timezone:/etc/timezone:ro`  
source: https://community.home-assistant.io/t/timezone-setting-in-appdaemon/71756/13

https://appdaemon.readthedocs.io/en/latest/DOCKER_TUTORIAL.html

