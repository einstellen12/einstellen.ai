from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging
from .models import Interview, Report, Question, Transcript
from .services.webrtc import start_webrtc_session
from .services.youtube import upload_to_youtube
from django.db import models
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import uuid

logger = logging.getLogger('interview')

class StartInterviewView(APIView):
    async def post(self, request):  # Changed to async
        if not hasattr(request, 'user_id'):
            return Response({"error": "Authentication required", "details": "User not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            data = request.data
            interviewer_id = request.user_id
            candidate_id = data.get('candidate_id')
            if not candidate_id:
                return Response({"error": "Invalid data", "details": "candidate_id is required"}, status=status.HTTP_400_BAD_REQUEST)

            interview = await Interview.objects.acreate(  # Use async create
                candidate_id=candidate_id,
                interviewer_id=interviewer_id
            )
            offer = await start_webrtc_session(interview.id)  # Changed to await
            interview_link = f"/interview/{interview.id}/?link={interview.link}"
            logger.info(f"Started interview {interview.id} for user {interviewer_id}")
            return Response({
                'interview_id': interview.id,
                'webrtc_offer': offer,
                'link': interview_link
            }, status=status.HTTP_200_OK)
        except KeyError as e:
            logger.error(f"Missing required field: {e}")
            return Response({"error": "Invalid data", "details": f"Missing field: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Start interview failed: {e}")
            return Response({"error": "Start interview failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class EndInterviewView(APIView):
    def post(self, request, interview_id):
        if not hasattr(request, 'user_id'):
            return Response({"error": "Authentication required", "details": "User not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            interview = Interview.objects.get(id=interview_id)
            interview.end_time = models.DateTimeField(auto_now=True)
            interview.local_path = f'recordings/{interview_id}.mp4'
            interview.save()
            if not os.getenv('RUNNING_IN_CLOUD', False):
                logger.info(f"Stored recording locally for interview {interview_id} at {interview.local_path}")
            else:
                upload_to_youtube(interview.local_path, interview_id)
            logger.info(f"Ended interview {interview_id} by user {request.user_id}")
            return Response({'status': 'Interview ended', 'link': f"/interview/{interview.id}/?link={interview.link}"}, status=status.HTTP_200_OK)
        except Interview.DoesNotExist:
            logger.warning(f"Interview not found: {interview_id}")
            return Response({"error": "Not found", "details": "Interview does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"End interview failed: {e}")
            return Response({"error": "End interview failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GenerateReportView(APIView):
    def post(self, request, interview_id):
        if not hasattr(request, 'user_id'):
            return Response({"error": "Authentication required", "details": "User not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            interview = Interview.objects.get(id=interview_id)
            transcripts = Transcript.objects.filter(interview=interview)
            report, _ = Report.objects.update_or_create(
                interview=interview,
                candidate_id=interview.candidate_id,
                defaults={
                    'transcript_summary': ' '.join([t.content for t in transcripts]),
                    'ai_evaluation': Report.objects.filter(interview=interview).first().ai_evaluation if Report.objects.filter(interview=interview).exists() else 'N/A',
                    'interviewer_feedback': request.data.get('feedback', '')
                }
            )
            report_json = {
                'interview_id': interview.id,
                'candidate_id': str(report.candidate_id),
                'start_time': str(interview.start_time),
                'end_time': str(interview.end_time),
                'transcript_summary': report.transcript_summary,
                'ai_evaluation': report.ai_evaluation,
                'interviewer_feedback': report.interviewer_feedback,
                'questions_asked': list(Question.objects.filter(interview=interview, asked=True).values('content')),
                'questions_diverted': list(Question.objects.filter(interview=interview, diverted=True).values('content')),
                'link': f"/interview/{interview.id}/?link={interview.link}"
            }

            # Generate PDF
            styles = getSampleStyleSheet()
            pdf_path = f'reports/interview_{interview_id}_report.pdf'
            doc = SimpleDocTemplate(pdf_path, pagesize=letter)
            story = []
            for key, value in report_json.items():
                story.append(Paragraph(f"<b>{key.replace('_', ' ').title()}:</b> {str(value)}", styles['Normal']))
            doc.build(story)

            logger.info(f"Report generated for interview {interview_id} by user {request.user_id}, PDF saved at {pdf_path}")
            return Response(report_json, status=status.HTTP_200_OK)
        except Interview.DoesNotExist:
            logger.warning(f"Interview not found: {interview_id}")
            return Response({"error": "Not found", "details": "Interview does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return Response({"error": "Report generation failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class MarkQuestionView(APIView):
    def post(self, request, interview_id):
        if not hasattr(request, 'user_id'):
            return Response({"error": "Authentication required", "details": "User not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            data = request.data
            interview = Interview.objects.get(id=interview_id)
            Question.objects.filter(id=data['question_id'], interview_id=interview_id).update(
                asked=data['asked'],
                diverted=data.get('diverted', False)
            )
            logger.info(f"Question {data['question_id']} marked for interview {interview_id} by user {request.user_id}")
            return Response({'status': 'Question marked'}, status=status.HTTP_200_OK)
        except Interview.DoesNotExist:
            logger.warning(f"Interview not found: {interview_id}")
            return Response({"error": "Not found", "details": "Interview does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Question.DoesNotExist:
            logger.warning(f"Question {data.get('question_id')} not found for interview {interview_id}")
            return Response({"error": "Not found", "details": "Question does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except KeyError as e:
            logger.error(f"Missing required field: {e}")
            return Response({"error": "Invalid data", "details": f"Missing field: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Mark question failed: {e}")
            return Response({"error": "Mark question failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FetchCandidateReportsView(APIView):
    def get(self, request, candidate_id):
        if not hasattr(request, 'user_id'):
            return Response({"error": "Authentication required", "details": "User not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            try:
                candidate_id_uuid = uuid.UUID(candidate_id)
            except ValueError:
                return Response({"error": "Invalid candidate_id", "details": "Must be a valid UUID"}, status=status.HTTP_400_BAD_REQUEST)

            reports = Report.objects.filter(candidate_id=candidate_id_uuid).values()
            enriched_reports = [
                {**report, 'link': f"/interview/{report['interview_id']}/?link={Interview.objects.get(id=report['interview_id']).link}"}
                for report in reports
            ]
            logger.info(f"Fetched reports for candidate {candidate_id} by user {request.user_id}")
            return Response({'reports': enriched_reports}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Fetch Route reports failed: {e}")
            return Response({"error": "Fetch reports failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class InterviewPageView(APIView):
    def get(self, request, interview_id):
        if not hasattr(request, 'user_id'):
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        interview = Interview.objects.get(id=interview_id)
        provided_link = request.GET.get('link', '')
        if str(provided_link) != str(interview.link) and str(interview.interviewer_id) != str(request.user_id) and str(interview.candidate_id) != str(request.user_id):
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        offer = start_webrtc_session(interview_id)
        return Response({"interview_id": interview_id, "link": interview.link, "webrtc_offer": offer})

class RegenerateInterviewLinkView(APIView):
    def post(self, request, interview_id):
        if not hasattr(request, 'user_id'):
            return Response({"error": "Authentication required", "details": "User not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            interview = Interview.objects.get(id=interview_id)
            # Only allow interviewer or candidate to regenerate the link
            if str(interview.interviewer_id) != str(request.user_id) and str(interview.candidate_id) != str(request.user_id):
                logger.warning(f"Unauthorized attempt to regenerate link for interview {interview_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not have permission to regenerate this link"}, status=status.HTTP_403_FORBIDDEN)

            interview.link = uuid.uuid4()
            interview.save()
            new_link = f"/interview/{interview.id}/?link={interview.link}"
            logger.info(f"Regenerated link for interview {interview_id} by user {request.user_id}: {new_link}")
            return Response({'link': new_link}, status=status.HTTP_200_OK)
        except Interview.DoesNotExist:
            logger.warning(f"Interview not found: {interview_id}")
            return Response({"error": "Not found", "details": "Interview does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Link regeneration failed: {e}")
            return Response({"error": "Link regeneration failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)