# from youtube_upload.client import YoutubeUploader
from django.db import connection
import logging

logger = logging.getLogger('interview')

def upload_to_youtube(video_path, interview_id):
    # try:
    #     uploader = YoutubeUploader('client_secrets.json')
    #     link = uploader.upload(video_path, title=f'Interview_{interview_id}', privacy='unlisted')
    #     with connection.cursor() as cursor:
    #         cursor.execute("UPDATE interviews SET youtube_link = %s WHERE id = %s", [link, interview_id])
    #     logger.info(f"Video uploaded for interview {interview_id}: {link}")
    # except Exception as e:
    #     logger.error(f"Failed to upload video for interview {interview_id}: {e}")
    pass