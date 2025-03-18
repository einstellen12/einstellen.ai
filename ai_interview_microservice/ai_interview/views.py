from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
import requests
from .models import Interview, QuestionAnswer, FeedbackReport
from .serializers import InterviewSerializer, FeedbackReportSerializer
from .logger import logger
from .ai_engine import generate_initial_question

class StartInterviewView(APIView):
    def post(self, request):
        try:
            subscription_id = request.data.get('subscription_id')
            candidate_id = request.data.get('candidate_id')
            job_id = request.data.get('job_id')

            credits_response = requests.post(
                f"http://billing-service/subscriptions/{subscription_id}/consume-credits/",
                json={'credits': 1},
                headers={'Authorization': f'Bearer {request.headers.get("Authorization")}'}
            )
            if credits_response.status_code != 200:
                return Response(credits_response.json(), status=credits_response.status_code)

            interview = Interview.objects.create(
                tenant_id=request.tenant_id,
                subscription_id=subscription_id,
                candidate_id=candidate_id,
                status='in_progress',
                start_time=timezone.now()
            )
            initial_question = generate_initial_question(candidate_id, job_id)
            QuestionAnswer.objects.create(interview=interview, question=initial_question)
            serializer = InterviewSerializer(interview)
            logger.info(f"Interview started: {interview.id}")
            return Response({"interview": serializer.data, "initial_question": initial_question}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Interview start failed: {e}")
            return Response({"error": "Start failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EndInterviewView(APIView):
    def post(self, request, interview_id):
        try:
            interview = Interview.objects.get(id=interview_id, tenant_id=request.tenant_id)
            interview.status = 'completed'
            interview.end_time = timezone.now()
            interview.save()

            qas = interview.questions_answers.all()
            detailed_scores = {}
            total_score = 0
            num_scored = 0
            comments = []

            for qa in qas:
                if qa.score is not None:
                    detailed_scores[str(qa.id)] = {
                        'question': qa.question,
                        'score': qa.score,
                        'is_deviated': qa.is_deviated
                    }
                    total_score += qa.score
                    num_scored += 1
                    if qa.is_deviated:
                        comments.append(f"Interviewer deviated from AI question: {qa.question}")
                else:
                    comments.append(f"Unscored question: {qa.question}")

            overall_score = total_score / num_scored if num_scored > 0 else 0
            feedback_comments = "\n".join(comments) or "No deviations or unscored questions."

            feedback = FeedbackReport.objects.create(
                interview=interview,
                overall_score=overall_score,
                detailed_scores=detailed_scores,
                comments=feedback_comments
            )
            serializer = FeedbackReportSerializer(feedback)
            logger.info(f"Interview ended: {interview_id}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Interview.DoesNotExist:
            logger.warning(f"Interview not found: {interview_id}")
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Interview end failed: {e}")
            return Response({"error": "End failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)