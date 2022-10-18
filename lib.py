import sys
import datetime
from os import path
import os
import json
import time
import random
import shutil
import wave
import contextlib
import re
import requests
import math

import deepspeech as ds
import speech_recognition as sr

from moviepy.editor import AudioFileClip

import numpy as np

import pandas as pd

from selenium import webdriver
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

DATA_DIR = './data'
TMP_DIR = './tmp'
TRANSCRIPTIONS_PATH = path.join('./data', 'video_transcriptions.json')
COMMENTS_CLEANED_PATH = path.join(DATA_DIR, 'cleaned_comments.csv')
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:103.0) Gecko/20100101 Firefox/103.0'
textified = ''

comments_df: pd.DataFrame
videos_df: pd.DataFrame
browser = 0
WAIT_BASE_TIME = 3
TIMEOUT = 30

def load_comments():
  comments_path = path.join(DATA_DIR, 'comments.json')

  global comments_df
  comments_df = pd.read_json(
    comments_path,
    lines = True
  )

  comments_df = comments_df.apply(
    clean_comments_rows,
    axis = 1
  )

  return comments_df

def clean_comments_rows(row):
  for idx in row.index.tolist():
    if idx != 'replies':
      row[idx] = row[idx][0]

  if str(row['replies']) != 'nan':
    for reply in row['replies']:
      for key in reply.keys():
        reply[key] = reply[key][0]

  return row

def load_videos():
  videos_path = path.join(DATA_DIR, 'videos.json')

  global videos_df
  videos_df = pd.read_json(
    videos_path,
    lines = True
  )

  videos_df = videos_df.apply(
    clean_videos_rows,
    axis = 1
  )

  return videos_df

def clean_videos_rows(row):
  for idx in row.index.tolist():
    row[idx] = row[idx][0]

  row['dislikes'] = row['dislikes'].replace('\n', '')
  row['likes'] = row['likes'].replace('\n', '')

  return row

def compute_average_comments_per_video():
  total_comments = len(comments_df)
  total_videos = len(videos_df)

  return total_comments / total_videos

def compute_median_comments_video():
  comment_numbers = []
  for video in comments_df['video'].unique():
    comment_numbers.append(
      len(
        comments_df.loc[
          comments_df['video'] == video
        ]
      )
    )

  comment_numbers.sort()
  print(
    comment_numbers[
      len(comment_numbers) // 2
    ]
  )

def get_comments_from_video(video):
  global comments_df
  return comments_df.loc[
    comments_df['video'] == video
  ]

def search_for_comment_containing(term):
  global comments_df

  return comments_df[
    comments_df['content'].str.contains(term)
  ]

def comments_by_author(author):
  global comments_df
  return comments_df[
    comments_df['author'] == author
  ]


"""
harvest transcripts
"""

def harvest_transcripts():
  initialize_selenium_instance()

  videos_df.loc[125:250, :].apply(
    _harvest_transcripts,
    axis = 1
  )

def initialize_selenium_instance():
  global browser
  profile = webdriver.FirefoxProfile()
  profile.set_preference('general.useragent.override', USER_AGENT)

  browser = webdriver.Firefox(
    profile,
    service=FirefoxService(GeckoDriverManager().install())
  )

def _harvest_transcripts(row):
  url = row['url']
  title = row['title']

  entries = []
  index_transcript(url, title, entries)

  return row

def index_transcript(url, title, entries):
  global browser

  get_and_wait(url)
  try:
    video_source = WebDriverWait(browser, timeout=TIMEOUT).until(
      lambda d: d.find_element(
        By.CSS_SELECTOR,
        'video#player > source[type="video/mp4"]'
      )
    )
    video_source = video_source.get_attribute('src')

    download_video(title, video_source)

  except Exception as e:
      print(e)
      with open(TRANSCRIPTIONS_PATH, 'a+') as f:
        f.write(json.dumps(
          {
            'title': title,
            'transcription': '[MISSING]'
          }
        ) + '\n')


  return 0

def download_video(title, video_source):
  global TMP_DIR
  mp4_dir = path.join(TMP_DIR, ''.join(filter(str.isalnum, title)))
  if os.path.exists(mp4_dir):
    shutil.rmtree(mp4_dir)
  os.mkdir(mp4_dir)
  mp4_path = path.join(mp4_dir, 'audio.mp4')
  transcribed_audio = path.join(mp4_dir, 'audio.wav')

  os.system(
    f'curl {video_source} --output {mp4_path}'
  )

  '''
  r = requests.get(video_source)
  with open(mp4_path, 'w+') as f:
    for chunk in r.iter_content(chunk_size=255):
      if chunk:
        f.write(chunk)
  '''

  audioclip = AudioFileClip(mp4_path)
  audioclip.write_audiofile(transcribed_audio)
  duration: float
  with contextlib.closing(wave.open(transcribed_audio, 'r')) as f:
    frames = f.getnframes()
    rate = f.getframerate()
    duration = frames / float(rate)

  total_duration = math.ceil(duration / 60)

  r = sr.Recognizer()
  textified = ''
  for i in range(0, total_duration):
    try:
      with sr.AudioFile(transcribed_audio) as source:
        audio = r.record(source, offset=i*60,duration=60)
        textified += ' ' + r.recognize_google(audio)
    except sr.UnknownValueError:
      textified += ' [UNINTELLIGIBLE]'

  with open(TRANSCRIPTIONS_PATH, 'a+') as f:
    f.write(json.dumps(
      {
        'title': title,
        'transcription': textified
      }
    ) + '\n')

  shutil.rmtree(mp4_dir)




def get_and_wait(url):
  global browser
  random_wait()
  browser.get(url)

def random_wait():
  more_or_less = round(random.random()) + 1
  more_or_less = -1 ** more_or_less
  noise=random.uniform(0.5, 1.5) * more_or_less

  return time.sleep(WAIT_BASE_TIME + noise)

