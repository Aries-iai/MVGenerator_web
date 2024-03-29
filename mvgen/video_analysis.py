from __future__ import print_function
import os, glob, shutil, sys
import time
import re
import pandas as pd
import subprocess
from collections import Counter

# Standard PySceneDetect imports:
from scenedetect.video_manager import VideoManager
from scenedetect.scene_manager import SceneManager

# For caching detection metrics and saving/loading to a stats file
from scenedetect.stats_manager import StatsManager

# For content-aware scene detection:
from scenedetect.detectors.content_detector import ContentDetector

# For splitting video:
import scenedetect.video_splitter as video_splitter

from .config import (
    VIDEO_SPLIT_TEMPLATE,
    FILE_SCENE_LENGH, FILE_SCENE_NUMBER
) 


def find_scenes(video_path):
    """ 
    Split video into scenes (one camera movement)

    Args:
        video_path (str): path of video, e.g. 'ok.mp4' 

    Returns:
        list[tuple[int, int]]: list of (startTimeCode, endTimeCode) for scene in video  
            e.g. [(1,10),(10,23),(23,67),(67,129)] 
    """
    start_time = time.time()
    print("Analyzing video "+video_path)

    # type: (str) -> List[Tuple[FrameTimecode, FrameTimecode]]
    video_manager = VideoManager([video_path])
    stats_manager = StatsManager()

    # Pass StatsManager to SceneManager to accelerate computing time
    scene_manager = SceneManager(stats_manager)

    # Add ContentDetector algorithm (each detector's constructor
    # takes detector options, e.g. threshold).
    scene_manager.add_detector(ContentDetector())
    base_timecode = video_manager.get_base_timecode()

    # We save our stats file to {VIDEO_PATH}.stats.csv.
    stats_file_path = '%s.stats.csv' % (video_path)

    scene_list = []

    folder = os.path.splitext(video_path)[0]

    if os.path.exists(folder):
        print('--- STOP : The folder for this video already exists, it is probably already split.')

    else:
        try:
            # If stats file exists, load it.
            if os.path.exists(stats_file_path):
                # Read stats from CSV file opened in read mode:
                with open(stats_file_path, 'r') as stats_file:
                    stats_manager.load_from_csv(stats_file, base_timecode)
            
            if video_splitter.is_ffmpeg_available():
                # Set downscale factor to improve processing speed.
                video_manager.set_downscale_factor()

                # Start video_manager.
                video_manager.start()

                # Perform scene detection on video_manager.
                scene_manager.detect_scenes(frame_source=video_manager)

                # Obtain list of detected scenes.
                scene_list = scene_manager.get_scene_list(base_timecode)
                # Each scene is a tuple of (start, end) FrameTimecodes.

                print('%s scenes obtained' % len(scene_list))

                if len(scene_list)>0:
                    # STATISTICS : Store scenes length
                    with open(FILE_SCENE_LENGH,'a', encoding='utf-8') as myfile:
                       for i, scene in enumerate(scene_list):
                           myfile.write('%s, %d, %f\n' % (os.path.splitext(os.path.basename(video_path))[0], scene[1].get_frames()-scene[0].get_frames(), (scene[1]-scene[0]).get_seconds()))
                    
                    # STATISTICS : Store number of scenes
                    with open(FILE_SCENE_NUMBER,'a', encoding='utf-8') as myfile:
                        myfile.write('%s,%d\n'%(os.path.splitext(os.path.basename(video_path))[0],len(scene_list)))

                    # Split the video
                    print('Splitting the video. Put scenes in %s/%s'%(folder,VIDEO_SPLIT_TEMPLATE))
                    os.mkdir(folder)
                    video_splitter.split_video_ffmpeg([video_path], scene_list, folder+"/"+VIDEO_SPLIT_TEMPLATE+".mp4", os.path.basename(folder),suppress_output=True)
            
                print("-- Finished video splitting in {:.2f}s --".format(time.time() - start_time))
            else:
                print('Ffmpeg is not installed on your computer. Please install it before running this code')

        finally:
            video_manager.release()

    return scene_list


'''
Get video width and height
'''
def detect_crop(video_path):
    if os.path.exists(video_path):
        p = subprocess.Popen(
            ["ffmpeg", "-i", video_path, "-vf", "cropdetect=24:16:0", 
             "-ss", "10", "-vframes", "1000", "-y", "-f", "null", "-"], 
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        # -ss is how many frames we skip ahead before we start detecting. 
        # If the video has a very long intro, you might need to increase this considerably.
        # -vframes is how many samples (frames)
        # -vf means video filter "cropdetect", which is the filter we use to do the actual detecting.
        
        infos = p.stderr.read().decode('utf-8')
        allCrops = re.findall("crop=\S+", infos)
        mostCommonCrop = Counter(allCrops).most_common(1)
        strCrop = mostCommonCrop[0][0][5:].split(":")
        return(strCrop[0]+"x"+strCrop[1])
    else:
        return ""


'''
Resize videos
3 options : crop in, rescale, crop out (pad)
'''
def resize_video(video_path, option):
    if os.path.exists(video_path):
        temp_path = os.path.splitext(video_path)[0]+"_temp"+os.path.splitext(video_path)[1]
        os.rename(video_path,temp_path)
        try:
            subprocess.call(["ffmpeg", "-loglevel", "error",  "-i", temp_path, "-vf", option, video_path])

            # delete original video
            os.remove(temp_path)
            
        except:
            print("Problem while running ffmpeg")
            os.rename(temp_path,video_path)


'''
Get video length
'''
def get_video_length(video_path):
    if os.path.exists(video_path):
        duration = subprocess.check_output(['ffprobe', '-i', video_path, '-show_entries', 'format=duration', '-v', 'quiet', '-of', 'csv=%s' % ("p=0")])
        return duration.decode('utf-8')[:-1] # remove \n at end
    else:
        return ""


'''
Get real video resolution (outside of black bars)
'''
def get_video_resolution(video_path):
    if os.path.exists(video_path):
        duration = subprocess.check_output(['ffprobe', '-i', video_path, '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-v', 'error', '-of', 'csv=%s' % ("s=x:p=0")])
        return duration.decode('utf-8')[:-1] # remove \n at end
    else:
        return ""


def main(*args):
    for vid in sorted(glob.glob(os.path.join(args[1], '*.mp4'))):
        find_scenes(vid)

if __name__ == "__main__":
    main(*sys.argv)
