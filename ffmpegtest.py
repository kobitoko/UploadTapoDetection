from ffmpeg import FFmpeg, Progress

#taken from https://pypi.org/project/python-ffmpeg/
def main():
    ffmpeg = (
        FFmpeg()
        .option("y")
        .input("",
            rtsp_transport="tcp",
            rtsp_flags="prefer_tcp",
        )
        .output("output.mp4", vcodec="copy")
    )
    # or if its within a class, can do something like:
    #self.ffmpeg.on("progress", self.time_to_terminate)
    @ffmpeg.on("progress")
    def time_to_terminate(progress: Progress):
        if progress.frame > 200:
            ffmpeg.terminate()

    ffmpeg.execute()


if __name__ == "__main__":
    main()