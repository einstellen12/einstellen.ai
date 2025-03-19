from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
import asyncio
import os
import logging

logger = logging.getLogger('interview')
pcs = set()

async def save_recording(track, interview_id):
    output_path = f'recordings/{interview_id}.mp4'
    with open(output_path, 'wb') as f:
        while True:
            frame = await track.recv()
            f.write(frame.to_bytes())

async def start_webrtc_session(interview_id):  # Changed to async
    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on('track')
    def on_track(track):
        logger.info(f"Received track: {track.kind}")
        if track.kind == 'video' or track.kind == 'audio':
            asyncio.ensure_future(save_recording(track, interview_id))

    await pc.setLocalDescription(await pc.createOffer())
    offer_data = {'sdp': pc.localDescription.sdp, 'type': pc.localDescription.type}
    logger.info(f"WebRTC offer created for interview {interview_id}")
    return offer_data