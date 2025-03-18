from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Company, Job, Application
from .serializers import CompanySerializer, JobSerializer, ApplicationSerializer
from .logger import logger
from audit.models import AuditLog
from .matching import calculate_match_score
import requests

class CreateCompanyView(APIView):
    def post(self, request):
        try:
            data = request.data.copy()
            data['tenant_id'] = request.tenant_id
            serializer = CompanySerializer(data=data)
            if not serializer.is_valid():
                logger.warning(f"Company creation validation failed: {serializer.errors}")
                return Response({"error": "Validation failed", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            company = serializer.save()
            request.audit_action = "Create Company"
            request.audit_details = {"company_id": str(company.id)}
            logger.info(f"Company created: {company.id}")
            return Response({"company_id": str(company.id)}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Company creation failed: {e}")
            return Response({"error": "Creation failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CreateJobView(APIView):
    def post(self, request):
        try:
            company = Company.objects.get(id=request.data.get('company_id'), tenant_id=request.tenant_id)
            data = request.data.copy()
            data['company'] = company.id
            serializer = JobSerializer(data=data)
            if not serializer.is_valid():
                logger.warning(f"Job creation validation failed: {serializer.errors}")
                return Response({"error": "Validation failed", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            job = serializer.save()
            request.audit_action = "Create Job"
            request.audit_details = {"job_id": str(job.id)}
            logger.info(f"Job created: {job.id}")
            return Response({"job_id": str(job.id)}, status=status.HTTP_201_CREATED)
        except Company.DoesNotExist:
            logger.warning(f"Company not found: {request.data.get('company_id')}")
            return Response({"error": "Not found", "details": "Company does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Job creation failed: {e}")
            return Response({"error": "Creation failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetJobView(APIView):
    def get(self, request, job_id):
        try:
            job = Job.objects.get(id=job_id, company__tenant_id=request.tenant_id)
            serializer = JobSerializer(job)
            request.audit_action = "Get Job"
            request.audit_details = {"job_id": str(job_id)}
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Job.DoesNotExist:
            logger.warning(f"Job not found: {job_id}")
            return Response({"error": "Not found", "details": "Job does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Job retrieval failed: {e}")
            return Response({"error": "Retrieval failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ListJobsView(APIView):
    def get(self, request):
        try:
            jobs = Job.objects.filter(company__tenant_id=request.tenant_id)
            serializer = JobSerializer(jobs, many=True)
            request.audit_action = "List Jobs"
            request.audit_details = {"tenant_id": str(request.tenant_id)}
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Job listing failed: {e}")
            return Response({"error": "Listing failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ApplyForJobView(APIView):
    def post(self, request, job_id):
        try:
            job = Job.objects.get(id=job_id, company__tenant_id=request.tenant_id)
            data = request.data.copy()
            data['job'] = job.id
            data['candidate_id'] = request.user_id
            
            # Fetch candidate profile for matching
            profile_response = requests.get(
                f"http://candidate-profile-service/candidates/{request.user_id}/",
                headers={"Authorization": f"Bearer {request.headers.get('Authorization', '').replace('Bearer ', '')}"}
            )
            if profile_response.status_code != 200:
                logger.warning(f"Failed to fetch candidate profile: {profile_response.text}")
                return Response({"error": "Profile fetch failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            candidate_profile = profile_response.json()
            candidate_skills = [skill['skill_name'] for skill in candidate_profile.get('skills', [])]
            candidate_text = " ".join([candidate_profile.get('first_name', ''), candidate_profile.get('last_name', ''),
                                      " ".join([edu['degree'] for edu in candidate_profile.get('education', [])])])
            match_score = calculate_match_score(job.key_skills, candidate_skills, job.description, candidate_text)
            data['match_score'] = match_score

            serializer = ApplicationSerializer(data=data)
            if not serializer.is_valid():
                logger.warning(f"Application validation failed: {serializer.errors}")
                return Response({"error": "Validation failed", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            application = serializer.save()
            request.audit_action = "Apply for Job"
            request.audit_details = {"application_id": str(application.id), "job_id": str(job_id)}
            logger.info(f"Application created: {application.id}")
            return Response({"application_id": str(application.id), "match_score": match_score}, status=status.HTTP_201_CREATED)
        except Job.DoesNotExist:
            logger.warning(f"Job not found: {job_id}")
            return Response({"error": "Not found", "details": "Job does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Application creation failed: {e}")
            return Response({"error": "Creation failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ListApplicationsView(APIView):
    def get(self, request):
        try:
            applications = Application.objects.filter(job__company__tenant_id=request.tenant_id)
            serializer = ApplicationSerializer(applications, many=True)
            request.audit_action = "List Applications"
            request.audit_details = {"tenant_id": str(request.tenant_id)}
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Application listing failed: {e}")
            return Response({"error": "Listing failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UpdateApplicationStatusView(APIView):
    def put(self, request, application_id):
        try:
            application = Application.objects.get(id=application_id, job__company__tenant_id=request.tenant_id)
            serializer = ApplicationSerializer(application, data={'status': request.data.get('status')}, partial=True)
            if not serializer.is_valid():
                logger.warning(f"Status update validation failed: {serializer.errors}")
                return Response({"error": "Validation failed", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            serializer.save()
            request.audit_action = "Update Application Status"
            request.audit_details = {"application_id": str(application_id), "new_status": request.data.get('status')}
            logger.info(f"Application status updated: {application_id}")
            return Response({"message": "Status updated successfully"}, status=status.HTTP_200_OK)
        except Application.DoesNotExist:
            logger.warning(f"Application not found: {application_id}")
            return Response({"error": "Not found", "details": "Application does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Status update failed: {e}")
            return Response({"error": "Update failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetMatchingCandidatesView(APIView):
    def get(self, request, job_id):
        try:
            job = Job.objects.get(id=job_id, company__tenant_id=request.tenant_id)
            applications = Application.objects.filter(job=job)
            matches = []

            for app in applications:
                profile_response = requests.get(
                    f"http://candidate-profile-service/candidates/{app.candidate_id}/",
                    headers={"Authorization": f"Bearer {request.headers.get('Authorization', '').replace('Bearer ', '')}"}
                )
                if profile_response.status_code == 200:
                    candidate_profile = profile_response.json()
                    candidate_skills = [skill['skill_name'] for skill in candidate_profile.get('skills', [])]
                    candidate_text = " ".join([candidate_profile.get('first_name', ''), candidate_profile.get('last_name', ''),
                                              " ".join([edu['degree'] for edu in candidate_profile.get('education', [])])])
                    match_score = calculate_match_score(job.key_skills, candidate_skills, job.description, candidate_text)
                    matches.append({"candidate_id": str(app.candidate_id), "match_score": match_score})

            matches.sort(key=lambda x: x['match_score'], reverse=True)
            request.audit_action = "Get Matching Candidates"
            request.audit_details = {"job_id": str(job_id)}
            return Response(matches, status=status.HTTP_200_OK)
        except Job.DoesNotExist:
            logger.warning(f"Job not found: {job_id}")
            return Response({"error": "Not found", "details": "Job does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Matching candidates retrieval failed: {e}")
            return Response({"error": "Retrieval failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)