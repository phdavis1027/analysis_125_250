from lib import *

comments_df = load_comments()
videos_df = load_videos()

harvest_transcripts()

comments_df.to_csv(COMMENTS_CLEANED_PATH)

