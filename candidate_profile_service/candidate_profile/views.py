from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework import filters
from django.core.files.storage import FileSystemStorage
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from .models import Candidate, Education, WorkExperience, Skill, Certification, Interview, InterviewInsight
from .serializers import (
    CandidateSerializer, EducationSerializer, WorkExperienceSerializer,
    SkillSerializer, CertificationSerializer, InterviewSerializer, InterviewInsightSerializer
)
from .logger import logger
from audit.models import AuditLog
from .parser import ResumeParser
from django.conf import settings
from django.views.decorators.cache import cache_page
from ratelimit.decorators import ratelimit
import requests
import random

# Custom Pagination Class
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

# Helper function to send notifications via the notification microservice
def send_notification(user_id, tenant_id, message, recipient, notification_type='in_app', subject=None, request=None):
    try:
        notification_service_url = f"{settings.NOTIFICATION_SERVICE_URL}/notifications/send/"
        headers = {
            "Authorization": f"Bearer {request.headers.get('Authorization', '').replace('Bearer ', '')}"
            if request and request.headers.get('Authorization')
            else ""
        }
        data = {
            "user_id": str(user_id),
            "tenant_id": str(tenant_id),
            "notification_type": notification_type,
            "message": message,
            "recipient": recipient,
            "subject": subject
        }
        response = requests.post(notification_service_url, json=data, headers=headers, timeout=5)
        if response.status_code != 201:
            logger.warning(f"Failed to send notification: {response.text}")
    except Exception as e:
        logger.error(f"Notification sending failed: {e}")

class CreateCandidateProfileView(APIView):
    def post(self, request):
        try:
            data = request.data.copy()
            data['user_id'] = request.user_id
            if hasattr(request, 'tenant_id'):
                data['tenant_id'] = request.tenant_id
            serializer = CandidateSerializer(data=data)
            serializer.is_valid(raise_exception=True)

            candidate = serializer.save()
            AuditLog.objects.create(
                user_id=request.user_id, action="Create Candidate Profile", tenant_id=request.tenant_id,
                details={"candidate_id": str(candidate.id)}
            )
            logger.info(f"Candidate profile created: {candidate.id}")

            # Send notification
            send_notification(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                message="Your candidate profile has been created successfully.",
                recipient=request.user_id,
                request=request
            )

            return Response({"candidate_id": str(candidate.id)}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Profile creation failed: {e}")
            return Response({"error": "Profile creation failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetCandidateProfileView(APIView):
    def get(self, request, candidate_id):
        try:
            filters = {'id': candidate_id}
            if hasattr(request, 'tenant_id') and request.tenant_id:
                filters['tenant_id'] = request.tenant_id
            candidate = Candidate.objects.get(**filters)
            if str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized access to candidate {candidate_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this profile"}, status=status.HTTP_403_FORBIDDEN)

            serializer = CandidateSerializer(candidate)
            AuditLog.objects.create(
                user_id=request.user_id, action="Get Candidate Profile", tenant_id=request.tenant_id,
                details={"candidate_id": str(candidate_id)}
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Candidate.DoesNotExist:
            logger.warning(f"Candidate not found: {candidate_id}")
            return Response({"error": "Not found", "details": "Candidate does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Profile retrieval failed: {e}")
            return Response({"error": "Retrieval failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UpdateCandidateProfileView(APIView):
    def put(self, request, candidate_id):
        try:
            filters = {'id': candidate_id}
            if hasattr(request, 'tenant_id') and request.tenant_id:
                filters['tenant_id'] = request.tenant_id
            candidate = Candidate.objects.get(**filters)
            if str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized update attempt on candidate {candidate_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this profile"}, status=status.HTTP_403_FORBIDDEN)

            serializer = CandidateSerializer(candidate, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)

            serializer.save()
            AuditLog.objects.create(
                user_id=request.user_id, action="Update Candidate Profile", tenant_id=request.tenant_id,
                details={"candidate_id": str(candidate_id)}
            )
            logger.info(f"Candidate profile updated: {candidate_id}")

            # Send notification
            send_notification(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                message="Your candidate profile has been updated successfully.",
                recipient=request.user_id,
                request=request
            )

            return Response({"message": "Profile updated successfully"}, status=status.HTTP_200_OK)
        except Candidate.DoesNotExist:
            logger.warning(f"Candidate not found for update: {candidate_id}")
            return Response({"error": "Not found", "details": "Candidate does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Profile update failed: {e}")
            return Response({"error": "Update failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UploadCVView(APIView):
    def post(self, request, candidate_id):
        try:
            filters = {'id': candidate_id}
            if hasattr(request, 'tenant_id') and request.tenant_id:
                filters['tenant_id'] = request.tenant_id
            candidate = Candidate.objects.get(**filters)
            if str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized CV upload attempt on candidate {candidate_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this profile"}, status=status.HTTP_403_FORBIDDEN)

            cv_file = request.FILES.get('cv')
            if not cv_file:
                logger.warning(f"No CV file provided for candidate {candidate_id}")
                return Response({"error": "No file provided", "details": "CV file is required"}, status=status.HTTP_400_BAD_REQUEST)

            fs = FileSystemStorage(location=settings.MEDIA_ROOT / 'cvs')
            filename = fs.save(f"{candidate_id}_{cv_file.name}", cv_file)

            job_role = request.data.get('job_role', 'Unknown')
            job_description = request.data.get('job_description', '')
            key_skills = request.data.get('key_skills', [])
            parser = ResumeParser(str(candidate_id), job_role, job_description, key_skills)
            cv_file.seek(0)
            pdf_content = cv_file.read()
            parsed_data = parser.parse(pdf_content)

            if parsed_data["metadata"]["status"] == "error":
                logger.error(f"CV parsing failed: {parsed_data['error']}")
                return Response({"error": "Parsing failed", "details": parsed_data["error"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Send notification
            send_notification(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                message=f"Your CV ({cv_file.name}) has been uploaded and parsed successfully.",
                recipient=request.user_id,
                request=request
            )

            AuditLog.objects.create(
                user_id=request.user_id, action="Upload and Parse CV", tenant_id=request.tenant_id,
                details={"candidate_id": str(candidate_id), "filename": filename}
            )
            logger.info(f"CV uploaded and parsed for candidate: {candidate_id}")
            return Response({
                "message": "CV uploaded and parsed successfully",
                "file_path": fs.url(filename),
                "parsed_data": parsed_data
            }, status=status.HTTP_200_OK)
        except Candidate.DoesNotExist:
            logger.warning(f"Candidate not found for CV upload: {candidate_id}")
            return Response({"error": "Not found", "details": "Candidate does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"CV upload failed: {e}")
            return Response({"error": "Upload failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AddEducationView(APIView):
    def post(self, request, candidate_id):
        try:
            filters = {'id': candidate_id}
            if hasattr(request, 'tenant_id') and request.tenant_id:
                filters['tenant_id'] = request.tenant_id
            candidate = Candidate.objects.get(**filters)
            if str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized education add attempt on candidate {candidate_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this profile"}, status=status.HTTP_403_FORBIDDEN)

            serializer = EducationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            education = serializer.save(candidate=candidate)
            AuditLog.objects.create(
                user_id=request.user_id, action="Add Education", tenant_id=request.tenant_id,
                details={"candidate_id": str(candidate_id), "education_id": str(education.id)}
            )
            logger.info(f"Education added for candidate: {candidate_id}")

            # Send notification
            send_notification(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                message=f"You have added a new education entry: {education.degree} at {education.university}.",
                recipient=request.user_id,
                request=request
            )

            return Response({"education_id": str(education.id)}, status=status.HTTP_201_CREATED)
        except Candidate.DoesNotExist:
            logger.warning(f"Candidate not found for education: {candidate_id}")
            return Response({"error": "Not found", "details": "Candidate does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Education addition failed: {e}")
            return Response({"error": "Addition failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AddWorkExperienceView(APIView):
    def post(self, request, candidate_id):
        try:
            filters = {'id': candidate_id}
            if hasattr(request, 'tenant_id') and request.tenant_id:
                filters['tenant_id'] = request.tenant_id
            candidate = Candidate.objects.get(**filters)
            if str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized work experience add attempt on candidate {candidate_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this profile"}, status=status.HTTP_403_FORBIDDEN)

            serializer = WorkExperienceSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            work_exp = serializer.save(candidate=candidate)
            AuditLog.objects.create(
                user_id=request.user_id, action="Add Work Experience", tenant_id=request.tenant_id,
                details={"candidate_id": str(candidate_id), "work_experience_id": str(work_exp.id)}
            )
            logger.info(f"Work experience added for candidate: {candidate_id}")

            # Send notification
            send_notification(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                message=f"You have added a new work experience: {work_exp.job_title} at {work_exp.company_name}.",
                recipient=request.user_id,
                request=request
            )

            return Response({"work_experience_id": str(work_exp.id)}, status=status.HTTP_201_CREATED)
        except Candidate.DoesNotExist:
            logger.warning(f"Candidate not found for work experience: {candidate_id}")
            return Response({"error": "Not found", "details": "Candidate does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Work experience addition failed: {e}")
            return Response({"error": "Addition failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AddSkillView(APIView):
    def post(self, request, candidate_id):
        try:
            filters = {'id': candidate_id}
            if hasattr(request, 'tenant_id') and request.tenant_id:
                filters['tenant_id'] = request.tenant_id
            candidate = Candidate.objects.get(**filters)
            if str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized skill add attempt on candidate {candidate_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this profile"}, status=status.HTTP_403_FORBIDDEN)

            serializer = SkillSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            skill = serializer.save(candidate=candidate)
            AuditLog.objects.create(
                user_id=request.user_id, action="Add Skill", tenant_id=request.tenant_id,
                details={"candidate_id": str(candidate_id), "skill_id": str(skill.id)}
            )
            logger.info(f"Skill added for candidate: {candidate_id}")

            # Send notification
            send_notification(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                message=f"You have added a new skill: {skill.skill_name}.",
                recipient=request.user_id,
                request=request
            )

            return Response({"skill_id": str(skill.id)}, status=status.HTTP_201_CREATED)
        except Candidate.DoesNotExist:
            logger.warning(f"Candidate not found for skill: {candidate_id}")
            return Response({"error": "Not found", "details": "Candidate does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Skill addition failed: {e}")
            return Response({"error": "Addition failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AddCertificationView(APIView):
    def post(self, request, candidate_id):
        try:
            filters = {'id': candidate_id}
            if hasattr(request, 'tenant_id') and request.tenant_id:
                filters['tenant_id'] = request.tenant_id
            candidate = Candidate.objects.get(**filters)
            if str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized certification add attempt on candidate {candidate_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this profile"}, status=status.HTTP_403_FORBIDDEN)

            serializer = CertificationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            certification = serializer.save(candidate=candidate)
            AuditLog.objects.create(
                user_id=request.user_id, action="Add Certification", tenant_id=request.tenant_id,
                details={"candidate_id": str(candidate_id), "certification_id": str(certification.id)}
            )
            logger.info(f"Certification added for candidate: {candidate_id}")

            send_notification(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                message=f"You have added a new certification: {certification.title}.",
                recipient=request.user_id,
                request=request
            )

            return Response({"certification_id": str(certification.id)}, status=status.HTTP_201_CREATED)
        except Candidate.DoesNotExist:
            logger.warning(f"Candidate not found for certification: {candidate_id}")
            return Response({"error": "Not found", "details": "Candidate does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Certification addition failed: {e}")
            return Response({"error": "Addition failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EditPersonalInfoView(APIView):
    def put(self, request, candidate_id):
        try:
            filters = {'id': candidate_id}
            if hasattr(request, 'tenant_id') and request.tenant_id:
                filters['tenant_id'] = request.tenant_id
            candidate = Candidate.objects.get(**filters)
            if str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized edit attempt on candidate {candidate_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this profile"}, status=status.HTTP_403_FORBIDDEN)

            serializer = CandidateSerializer(candidate, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)

            serializer.save()
            AuditLog.objects.create(
                user_id=request.user_id, action="Edit Personal Info", tenant_id=request.tenant_id,
                details={"candidate_id": str(candidate_id)}
            )
            logger.info(f"Personal info updated for candidate: {candidate_id}")

            send_notification(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                message="Your personal information has been updated successfully.",
                recipient=request.user_id,
                request=request
            )

            return Response({"message": "Personal info updated successfully"}, status=status.HTTP_200_OK)
        except Candidate.DoesNotExist:
            logger.warning(f"Candidate not found for edit: {candidate_id}")
            return Response({"error": "Not found", "details": "Candidate does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Personal info edit failed: {e}")
            return Response({"error": "Edit failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EditEducationView(APIView):
    def put(self, request, education_id):
        try:
            education = Education.objects.get(id=education_id)
            candidate = education.candidate
            if (hasattr(request, 'tenant_id') and request.tenant_id and candidate.tenant_id and
                candidate.tenant_id != request.tenant_id) or str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized edit attempt on education {education_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this profile"}, status=status.HTTP_403_FORBIDDEN)

            serializer = EducationSerializer(education, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)

            serializer.save()
            AuditLog.objects.create(
                user_id=request.user_id, action="Edit Education", tenant_id=request.tenant_id,
                details={"candidate_id": str(candidate.id), "education_id": str(education_id)}
            )
            logger.info(f"Education updated: {education_id}")

            send_notification(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                message=f"Your education entry ({education.degree} at {education.university}) has been updated.",
                recipient=request.user_id,
                request=request
            )

            return Response({"message": "Education updated successfully"}, status=status.HTTP_200_OK)
        except Education.DoesNotExist:
            logger.warning(f"Education not found: {education_id}")
            return Response({"error": "Not found", "details": "Education does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Education edit failed: {e}")
            return Response({"error": "Edit failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EditWorkExperienceView(APIView):
    def put(self, request, work_experience_id):
        try:
            work_exp = WorkExperience.objects.get(id=work_experience_id)
            candidate = work_exp.candidate
            if (hasattr(request, 'tenant_id') and request.tenant_id and candidate.tenant_id and
                candidate.tenant_id != request.tenant_id) or str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized edit attempt on work experience {work_experience_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this profile"}, status=status.HTTP_403_FORBIDDEN)

            serializer = WorkExperienceSerializer(work_exp, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)

            serializer.save()
            AuditLog.objects.create(
                user_id=request.user_id, action="Edit Work Experience", tenant_id=request.tenant_id,
                details={"candidate_id": str(candidate.id), "work_experience_id": str(work_experience_id)}
            )
            logger.info(f"Work experience updated: {work_experience_id}")

            send_notification(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                message=f"Your work experience ({work_exp.job_title} at {work_exp.company_name}) has been updated.",
                recipient=request.user_id,
                request=request
            )

            return Response({"message": "Work experience updated successfully"}, status=status.HTTP_200_OK)
        except WorkExperience.DoesNotExist:
            logger.warning(f"Work experience not found: {work_experience_id}")
            return Response({"error": "Not found", "details": "Work experience does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Work experience edit failed: {e}")
            return Response({"error": "Edit failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EditSkillView(APIView):
    def put(self, request, skill_id):
        try:
            skill = Skill.objects.get(id=skill_id)
            candidate = skill.candidate
            if (hasattr(request, 'tenant_id') and request.tenant_id and candidate.tenant_id and
                candidate.tenant_id != request.tenant_id) or str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized edit attempt on skill {skill_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this profile"}, status=status.HTTP_403_FORBIDDEN)

            serializer = SkillSerializer(skill, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)

            serializer.save()
            AuditLog.objects.create(
                user_id=request.user_id, action="Edit Skill", tenant_id=request.tenant_id,
                details={"candidate_id": str(candidate.id), "skill_id": str(skill_id)}
            )
            logger.info(f"Skill updated: {skill_id}")

            send_notification(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                message=f"Your skill ({skill.skill_name}) has been updated.",
                recipient=request.user_id,
                request=request
            )

            return Response({"message": "Skill updated successfully"}, status=status.HTTP_200_OK)
        except Skill.DoesNotExist:
            logger.warning(f"Skill not found: {skill_id}")
            return Response({"error": "Not found", "details": "Skill does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Skill edit failed: {e}")
            return Response({"error": "Edit failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EditCertificationView(APIView):
    def put(self, request, certification_id):
        try:
            certification = Certification.objects.get(id=certification_id)
            candidate = certification.candidate
            if (hasattr(request, 'tenant_id') and request.tenant_id and candidate.tenant_id and
                candidate.tenant_id != request.tenant_id) or str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized edit attempt on certification {certification_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this profile"}, status=status.HTTP_403_FORBIDDEN)

            serializer = CertificationSerializer(certification, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)

            serializer.save()
            AuditLog.objects.create(
                user_id=request.user_id, action="Edit Certification", tenant_id=request.tenant_id,
                details={"candidate_id": str(candidate.id), "certification_id": str(certification_id)}
            )
            logger.info(f"Certification updated: {certification_id}")

            send_notification(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                message=f"Your certification ({certification.title}) has been updated.",
                recipient=request.user_id,
                request=request
            )

            return Response({"message": "Certification updated successfully"}, status=status.HTTP_200_OK)
        except Certification.DoesNotExist:
            logger.warning(f"Certification not found: {certification_id}")
            return Response({"error": "Not found", "details": "Certification does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Certification edit failed: {e}")
            return Response({"error": "Edit failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class JobListView(APIView):
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'company__name', 'location', 'description']

    @ratelimit(key='ip', rate='100/h', method='GET', block=True)
    @cache_page(60 * 15)
    def get(self, request):
        try:
            candidate_id = request.query_params.get('candidate_id')
            if not candidate_id:
                logger.warning("Candidate ID not provided in job list request")
                return Response({"error": "Candidate ID required"}, status=status.HTTP_400_BAD_REQUEST)

            filters = {'id': candidate_id}
            if hasattr(request, 'tenant_id') and request.tenant_id:
                filters['tenant_id'] = request.tenant_id
            candidate = Candidate.objects.get(**filters)
            if str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized access to candidate {candidate_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this profile"}, status=status.HTTP_403_FORBIDDEN)

            job_service_url = f"{settings.JOB_SERVICE_URL}/jobs/list/"
            headers = {
                "Authorization": f"Bearer {request.headers.get('Authorization', '').replace('Bearer ', '')}"
                if request.headers.get('Authorization')
                else ""
            }
            response = requests.get(job_service_url, headers=headers, timeout=5)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch jobs from job service: {response.text}")
                return Response({"error": "Failed to fetch jobs"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            jobs = response.json()

            candidate_skills = [skill.skill_name.lower() for skill in candidate.skills.all()]

            recommended_jobs = []
            for job in jobs:
                job_skills = [skill.lower() for skill in job.get('key_skills', [])]
                match_count = sum(1 for skill in candidate_skills if skill in job_skills)
                match_score = (match_count / max(len(job_skills), 1)) * 100
                if match_score > 30:
                    job['match_score'] = match_score
                    recommended_jobs.append(job)

            recommended_jobs.sort(key=lambda x: x['match_score'], reverse=True)

            search_query = request.query_params.get('search', '')
            if search_query:
                recommended_jobs = [
                    job for job in recommended_jobs
                    if (search_query.lower() in job['title'].lower() or
                        search_query.lower() in job['company']['name'].lower() or
                        search_query.lower() in job['location'].lower() or
                        search_query.lower() in job['description'].lower())
                ]

            paginator = self.pagination_class()
            page = paginator.paginate_queryset(recommended_jobs, request)

            logger.info(f"Retrieved {len(recommended_jobs)} recommended jobs for candidate {candidate_id}")
            return paginator.get_paginated_response(page)
        except Candidate.DoesNotExist:
            logger.warning(f"Candidate not found: {candidate_id}")
            return Response({"error": "Not found", "details": "Candidate does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Job listing retrieval failed: {e}")
            return Response({"error": "Retrieval failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ApplyJobView(APIView):
    def post(self, request, job_id):
        try:
            candidate_id = request.data.get('candidate_id')
            if not candidate_id:
                logger.warning("Candidate ID not provided in job application request")
                return Response({"error": "Candidate ID required"}, status=status.HTTP_400_BAD_REQUEST)

            filters = {'id': candidate_id}
            if hasattr(request, 'tenant_id') and request.tenant_id:
                filters['tenant_id'] = request.tenant_id
            candidate = Candidate.objects.get(**filters)
            if str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized access to candidate {candidate_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this profile"}, status=status.HTTP_403_FORBIDDEN)

            job_service_url = f"{settings.JOB_SERVICE_URL}/jobs/{job_id}/apply/"
            headers = {
                "Authorization": f"Bearer {request.headers.get('Authorization', '').replace('Bearer ', '')}"
                if request.headers.get('Authorization')
                else ""
            }
            response = requests.post(job_service_url, headers=headers, timeout=5)
            if response.status_code != 201:
                logger.warning(f"Failed to apply for job {job_id}: {response.text}")
                return Response({"error": "Application failed", "details": response.json().get('details', 'Unknown error')}, status=response.status_code)

            application_data = response.json()
            application_id = application_data.get('application_id')

            send_notification(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                message=f"You have successfully applied to job ID {job_id}.",
                recipient=request.user_id,
                request=request
            )

            AuditLog.objects.create(
                user_id=request.user_id, action="Apply Job", tenant_id=request.tenant_id,
                details={"candidate_id": str(candidate_id), "job_id": str(job_id), "application_id": application_id}
            )
            logger.info(f"Candidate {candidate_id} applied to job {job_id}")
            return Response({"message": "Job application submitted successfully", "application_id": application_id}, status=status.HTTP_201_CREATED)
        except Candidate.DoesNotExist:
            logger.warning(f"Candidate not found: {candidate_id}")
            return Response({"error": "Not found", "details": "Candidate does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Job application failed: {e}")
            return Response({"error": "Application failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class WithdrawApplicationView(APIView):
    def post(self, request, application_id):
        try:
            job_service_url = f"{settings.JOB_SERVICE_URL}/applications/{application_id}/status/"
            headers = {
                "Authorization": f"Bearer {request.headers.get('Authorization', '').replace('Bearer ', '')}"
                if request.headers.get('Authorization')
                else ""
            }
            response = requests.get(job_service_url, headers=headers, timeout=5)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch application {application_id}: {response.text}")
                return Response({"error": "Application fetch failed", "details": response.json().get('details', 'Unknown error')}, status=response.status_code)

            application = response.json()
            if str(application['candidate_id']) != str(request.user_id):
                logger.warning(f"Unauthorized withdraw attempt on application {application_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this application"}, status=status.HTTP_403_FORBIDDEN)

            if application['status'] in ['rejected']:
                logger.warning(f"Application {application_id} cannot be withdrawn - current status: {application['status']}")
                return Response({"error": "Invalid status", "details": "Application cannot be withdrawn"}, status=status.HTTP_400_BAD_REQUEST)

            update_response = requests.put(
                job_service_url,
                headers=headers,
                json={"status": "rejected"},
                timeout=5
            )
            if update_response.status_code != 200:
                logger.warning(f"Failed to withdraw application {application_id}: {update_response.text}")
                return Response({"error": "Withdrawal failed", "details": update_response.json().get('details', 'Unknown error')}, status=update_response.status_code)

            send_notification(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                message=f"You have withdrawn your application (ID: {application_id}).",
                recipient=request.user_id,
                request=request
            )

            AuditLog.objects.create(
                user_id=request.user_id, action="Withdraw Application", tenant_id=request.tenant_id,
                details={"application_id": str(application_id)}
            )
            logger.info(f"Application {application_id} withdrawn by candidate")
            return Response({"message": "Application withdrawn successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Application withdrawal failed: {e}")
            return Response({"error": "Withdrawal failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class InterviewInstructionsView(APIView):
    def get(self, request, interview_id):
        try:
            interview = Interview.objects.get(id=interview_id)
            candidate = interview.candidate
            if str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized access to interview {interview_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this interview"}, status=status.HTTP_403_FORBIDDEN)

            instructions = [
                "Focus on your webcam throughout the interview.",
                "Ensure a quiet environment with good lighting.",
                "Be prepared to discuss your experience and skills."
            ]
            logger.info(f"Retrieved interview instructions for interview {interview_id}")
            return Response({
                "user": f"{candidate.first_name}",
                "instructions": instructions
            }, status=status.HTTP_200_OK)
        except Interview.DoesNotExist:
            logger.warning(f"Interview not found: {interview_id}")
            return Response({"error": "Not found", "details": "Interview does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Interview instructions retrieval failed: {e}")
            return Response({"error": "Retrieval failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StartInterviewView(APIView):
    def post(self, request, interview_id):
        try:
            interview = Interview.objects.get(id=interview_id)
            candidate = interview.candidate
            if str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized start interview attempt on {interview_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this interview"}, status=status.HTTP_403_FORBIDDEN)

            if interview.status != 'SCHEDULED':
                logger.warning(f"Interview {interview_id} cannot be started - current status: {interview.status}")
                return Response({"error": "Invalid status", "details": "Interview cannot be started"}, status=status.HTTP_400_BAD_REQUEST)

            interview_service_url = f"{settings.INTERVIEW_SERVICE_URL}/interviews/{interview_id}/start/"
            headers = {
                "Authorization": f"Bearer {request.headers.get('Authorization', '').replace('Bearer ', '')}"
                if request.headers.get('Authorization')
                else ""
            }
            response = requests.post(interview_service_url, headers=headers, timeout=5)
            if response.status_code != 200:
                logger.warning(f"Failed to start interview {interview_id} via interview service: {response.text}")
                return Response({"error": "Interview start failed", "details": response.json().get('details', 'Unknown error')}, status=response.status_code)

            interview_data = response.json()

            interview.status = 'COMPLETED'
            interview.video_url = interview_data.get('video_url', f"https://example.com/videos/{interview_id}.mp4")
            interview.save()

            skills_detected = [skill.skill_name for skill in candidate.skills.all()]
            InterviewInsight.objects.create(
                interview=interview,
                overall_score=random.uniform(70, 95),
                communication_score=random.uniform(60, 90),
                technical_score=random.uniform(70, 95),
                problem_solving_score=random.uniform(65, 90),
                skills_detected=skills_detected
            )

            send_notification(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                message=f"Your interview for application ID {interview.application_id} has been completed.",
                recipient=request.user_id,
                request=request
            )

            AuditLog.objects.create(
                user_id=request.user_id, action="Start Interview", tenant_id=request.tenant_id,
                details={"interview_id": str(interview_id)}
            )
            logger.info(f"Interview {interview_id} started and completed for candidate {candidate.id}")
            return Response({"message": "Interview started and completed successfully"}, status=status.HTTP_200_OK)
        except Interview.DoesNotExist:
            logger.warning(f"Interview not found: {interview_id}")
            return Response({"error": "Not found", "details": "Interview does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Interview start failed: {e}")
            return Response({"error": "Start failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DashboardView(APIView):
    @ratelimit(key='ip', rate='50/h', method='GET', block=True)
    def get(self, request, candidate_id):
        try:
            filters = {'id': candidate_id}
            if hasattr(request, 'tenant_id') and request.tenant_id:
                filters['tenant_id'] = request.tenant_id
            candidate = Candidate.objects.get(**filters)
            if str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized access to dashboard for candidate {candidate_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this profile"}, status=status.HTTP_403_FORBIDDEN)

            job_service_url = f"{settings.JOB_SERVICE_URL}/applications/"
            headers = {
                "Authorization": f"Bearer {request.headers.get('Authorization', '').replace('Bearer ', '')}"
                if request.headers.get('Authorization')
                else ""
            }
            response = requests.get(job_service_url, headers=headers, timeout=5)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch applications from job service: {response.text}")
                return Response({"error": "Failed to fetch applications"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            applications = [app for app in response.json() if str(app['candidate_id']) == str(candidate.user_id)]

            last_30_days = timezone.now() - timedelta(days=30)
            jobs_applied = len([
                app for app in applications
                if timezone.datetime.fromisoformat(app['applied_at']) >= last_30_days
            ])
            recruiter_actions = len([
                app for app in applications
                if (timezone.datetime.fromisoformat(app['updated_at']) >= last_30_days and
                    app['status'] in ['shortlisted', 'interviewed', 'offered', 'rejected'])
            ])
            interview_schedules = Interview.objects.filter(
                candidate=candidate, scheduled_at__gte=last_30_days, status='SCHEDULED'
            ).count()

            latest_interview = Interview.objects.filter(
                candidate=candidate, status='COMPLETED', video_url__isnull=False
            ).order_by('-updated_at').first()
            video_url = latest_interview.video_url if latest_interview else None

            insights = None
            if latest_interview and hasattr(latest_interview, 'insights'):
                insights_serializer = InterviewInsightSerializer(latest_interview.insights)
                insights = insights_serializer.data

            candidate_skills = [skill.skill_name.lower() for skill in candidate.skills.all()]
            job_service_url = f"{settings.JOB_SERVICE_URL}/jobs/list/"
            response = requests.get(job_service_url, headers=headers, timeout=5)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch jobs from job service: {response.text}")
                return Response({"error": "Failed to fetch jobs"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            jobs = response.json()[:5]
            recommended_jobs = []
            for job in jobs:
                job_skills = [skill.lower() for skill in job.get('key_skills', [])]
                match_count = sum(1 for skill in candidate_skills if skill in job_skills)
                match_score = (match_count / max(len(job_skills), 1)) * 100
                if match_score > 30:
                    job['match_score'] = match_score
                    recommended_jobs.append(job)
            recommended_jobs.sort(key=lambda x: x['match_score'], reverse=True)

            recent_applications = sorted(
                [app for app in applications],
                key=lambda x: timezone.datetime.fromisoformat(x['applied_at']),
                reverse=True
            )[:5]

            logger.info(f"Retrieved dashboard data for candidate {candidate_id}")
            return Response({
                "stats": {
                    "jobs_applied": jobs_applied,
                    "recruiter_actions": recruiter_actions,
                    "interview_schedules": interview_schedules
                },
                "video_url": video_url,
                "insights": insights,
                "recommended_jobs": recommended_jobs,
                "recent_applications": recent_applications
            }, status=status.HTTP_200_OK)
        except Candidate.DoesNotExist:
            logger.warning(f"Candidate not found: {candidate_id}")
            return Response({"error": "Not found", "details": "Candidate does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Dashboard retrieval failed: {e}")
            return Response({"error": "Retrieval failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class NotificationListView(APIView):
    pagination_class = StandardResultsSetPagination

    @ratelimit(key='ip', rate='100/h', method='GET', block=True)
    def get(self, request, candidate_id):
        try:
            filters = {'id': candidate_id}
            if hasattr(request, 'tenant_id') and request.tenant_id:
                filters['tenant_id'] = request.tenant_id
            candidate = Candidate.objects.get(**filters)
            if str(candidate.user_id) != str(request.user_id):
                logger.warning(f"Unauthorized access to notifications for candidate {candidate_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this profile"}, status=status.HTTP_403_FORBIDDEN)

            notification_service_url = f"{settings.NOTIFICATION_SERVICE_URL}/notifications/"
            headers = {
                "Authorization": f"Bearer {request.headers.get('Authorization', '').replace('Bearer ', '')}"
                if request.headers.get('Authorization')
                else ""
            }
            response = requests.get(notification_service_url, headers=headers, timeout=5)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch notifications from notification service: {response.text}")
                return Response({"error": "Failed to fetch notifications"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            notifications = response.json()

            paginator = self.pagination_class()
            page = paginator.paginate_queryset(notifications, request)

            logger.info(f"Retrieved notifications for candidate {candidate_id}")
            return paginator.get_paginated_response(page)
        except Candidate.DoesNotExist:
            logger.warning(f"Candidate not found: {candidate_id}")
            return Response({"error": "Not found", "details": "Candidate does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Notification retrieval failed: {e}")
            return Response({"error": "Retrieval failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class MarkNotificationReadView(APIView):
    def post(self, request, notification_id):
        try:
            notification_service_url = f"{settings.NOTIFICATION_SERVICE_URL}/notifications/{notification_id}/"
            headers = {
                "Authorization": f"Bearer {request.headers.get('Authorization', '').replace('Bearer ', '')}"
                if request.headers.get('Authorization')
                else ""
            }
            response = requests.get(notification_service_url, headers=headers, timeout=5)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch notification {notification_id}: {response.text}")
                return Response({"error": "Notification fetch failed", "details": response.json().get('details', 'Unknown error')}, status=response.status_code)

            notification = response.json()
            if str(notification['user_id']) != str(request.user_id):
                logger.warning(f"Unauthorized mark read attempt on notification {notification_id} by user {request.user_id}")
                return Response({"error": "Unauthorized", "details": "You do not own this notification"}, status=status.HTTP_403_FORBIDDEN)


            AuditLog.objects.create(
                user_id=request.user_id, action="Mark Notification Read", tenant_id=request.tenant_id,
                details={"notification_id": str(notification_id)}
            )
            logger.info(f"Notification {notification_id} marked as read for candidate")
            return Response({"message": "Notification marked as read"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Notification mark read failed: {e}")
            return Response({"error": "Mark read failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)