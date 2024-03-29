import os, glob, sys
import time
import re
import subprocess
import pandas as pd

from .config import STATISTICS_PATH
from .music_recognition import get_music_infos
from .video_analysis import detect_crop, get_video_length, resize_video, get_video_resolution

def differential(a,b):
    return (a-b)/a

'''
Harmonize videos on server
either put them display 640x360 or 640x272
'''
def harmonize_video(vidFile):
    print("\n--------- Harmonizing video %s --------"%vidFile )

    start_time = time.time()

    if os.path.exists(vidFile):
        crop_width, crop_height = map(int,detect_crop(vidFile).split("x")) # Size of video within the black bars
        real_width, real_height = map(int,get_video_resolution(vidFile).split("x")) # Size of video uncliding the black bars


        # Make videos ratio 16/9 (640x360)
        if crop_width/crop_height < 2:
            print("Video radio %.2f ---> format 16/9"%(crop_width/crop_height))
            
            # if too high : crop on top
            if (crop_width/crop_height) < 16/9-0.05:
                print("Cropping height ... ")
                resize_video(vidFile, "crop=%d:%d"%(crop_width,crop_width*9/16))

            # if too wide : crop on side
            elif (crop_width/crop_height) > 16/9+0.05:
                print("Cropping width ... ")
                resize_video(vidFile, "crop=%d:%d"%(crop_height*16/9,crop_height))

        
        # Make videos ratio 40/17 (640x272)
        else :
            print("Video radio %.2f ---> format 40/17"%(crop_width/crop_height))

            # if too high : crop on top
            if (crop_width/crop_height < 40/17-0.05):
                print("Cropping height ... ")
                resize_video(vidFile, "crop=%d:%d"%(crop_width,crop_width*17/40))

            # if too wide : crop on side
            elif (crop_width/crop_height > 40/17+0.05):
                print("Cropping width ... ")
                resize_video(vidFile, "crop=%d:%d"%(crop_height*40/17,crop_height))


        # If still have black bars that do not fit format 640x360 - 640x272 (allow error 0.025), remove them
        crop_width, crop_height = map(int,detect_crop(vidFile).split("x"))
        real_width, real_height = map(int,get_video_resolution(vidFile).split("x"))

        if (differential(real_width,crop_width)>0.025 or (differential(real_height,crop_height)>0.025 and 
            abs(differential(real_height, crop_height)-0.244)>0.025)): # format 640x272
            print("Removing remaining black bars ...")
            resize_video(vidFile, "crop=%d:%d"%(crop_width, crop_height))


        # Have final width 640
        real_width, real_height = map(int,get_video_resolution(vidFile).split("x"))

        if real_width != 640:

            if real_width/real_height > 16/9 + 0.05:
                print("Current width = %d. Scaling and padding to have 640x360 ..."%real_width)
                resize_video(vidFile, "scale=640:-2,pad=640:360:(ow-iw)/2:(oh-ih)/2")

            elif real_width/real_height < 16/9 - 0.05:
                print("Current width = %d. Scaling and cropping to have 640x360 ..."%real_width)
                resize_video(vidFile, "scale=640:-2,crop=640:360")

            else:
                print("Current width = %d. Scaling to have 640x360 ..."%real_width)
                resize_video(vidFile, "scale=640:-2")

        # Have final height 360
        else:
            real_width, real_height = map(int,get_video_resolution(vidFile).split("x"))

            if real_height > 360:
                print("Current height = %d. Cropping to have 360 ..."%real_height)
                resize_video(vidFile, "crop=640:360")

            elif real_height < 360:
                print("Current height = %d. Padding to have 360 ..."%real_height)
                resize_video(vidFile, "pad=640:360:(ow-iw)/2:(oh-ih)/2")

        
        print("Finished video reformatting in %.2f s"%(time.time() - start_time))
        if crop_width/crop_height < 2:
            return "16/9"
        else:
            return "40/17"
    else:
        print("%s : File not found"%vidFile)
        return ""


''' 
give in input the folder where all videos are (must contain / at end)
the audio files of the videos should have been extracted beforehand with ffmpeg
and put in the same folder 
'''
def database_info_to_csv(database_path, harmonize=True):
    data = []
    name, artist, genres, style, resolution, length = ("","","","","","")

    for vidFile in glob.glob(os.path.join(database_path, "*.mp4")):

        # Audio infos
        audFile = vidFile[:-3]+"mp3"
        if os.path.exists(audFile):
            name, artist, genres, style = get_music_infos(audFile)
        else:
            print("Audio file does not exist for video %s. Writing blank"%vidFile)
        
        # Video infos
        if harmonize:
            resolution = harmonize_video(vidFile)
        else:
            resolution = detect_crop(vidFile).replace('x', '/')
        
        length = get_video_length(vidFile)

        data.append((os.path.splitext(os.path.basename(vidFile))[0], name, artist, genres, style, resolution, length))

    colNames = "id, name, artist, genres, style, resolution, length".split(", ")
    df = pd.DataFrame(data, columns=colNames, dtype=object)
    df.to_csv(os.path.join(STATISTICS_PATH, "songs_on_server.csv"), 
              sep=";", float_format="%.3f", index=False)


'''
extract audio from given video
'''
def extract_audio(video_path):
    if os.path.exists(video_path):
        subprocess.Popen([
                "ffmpeg", "-i", video_path, 
                "-ab", "160k", "-ac", "2", "-ar", "44100",
                "-loglevel", "quiet", "-vn", f"{os.path.splitext(video_path)[0]}.mp3"
            ], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
    print(f"Extract mp3 for {video_path}")


if __name__ == "__main__":
    # 2. CREATE CSV INFO FILE
    database_info_to_csv(sys.argv[1], harmonize=True)

