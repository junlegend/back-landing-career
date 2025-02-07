import json, sys, hashlib, sha3

from django.http  import JsonResponse

from rest_framework.views import APIView

from drf_yasg.utils import swagger_auto_schema
from drf_yasg       import openapi

from global_variable import ADMIN_TOKEN
from recruits.models import Recruit, Stack, RecruitStack
from core.decorators import admin_only
from recruits.serializers import RecruitSerializer, RecruitQuerySerializer, RecruitCreateBodySerializer

class RecruitListView(APIView):
    parameter_token = openapi.Parameter (
                                        "Authorization", 
                                        openapi.IN_HEADER, 
                                        description = "access_token", 
                                        type        = openapi.TYPE_STRING,
                                        default     = ADMIN_TOKEN
    )

    recruits_get_response = openapi.Response("results", RecruitSerializer)

    @swagger_auto_schema(
        query_serializer = RecruitQuerySerializer,
        responses = {
            "200": recruits_get_response,
            "404": "NOT_FOUND"
        },
        operation_id = "채용공고 목록 조회",
        operation_description = "채용공고 목록을 조회합니다. 포지션별 필터링, 마감일/연봉 기준 정렬\n" +
                                "position_title: developer, designer, ..\n" +
                                "sort    : deadline-ascend, salary-descend\n" +
                                "DEFAULT : 모든 포지션, 최신순"
    )
    def get(self, request):
        position_title = request.GET.get("position_title", "")
        sort           = request.GET.get("sort", "created-descend")

        sort_dict = {
            "deadline-ascend" : "deadline",
            "salary-descend"  : "-maximum_salary",
            "created-descend" : "-created_at",
        }

        recruits = (Recruit.objects.prefetch_related('stacks')
                                    .filter(position_title__icontains=position_title)
                                    .order_by(sort_dict[sort], '-created_at')
                    )
            
        results = [
            {
                "id"             : recruit.id,
                "position"       : recruit.position,
                "position_title" : recruit.position_title,
                "work_type"      : recruit.work_type,
                "career_type"    : recruit.get_career_type_display(),
                "author"         : recruit.author,
                "job_openings"   : recruit.job_openings,
                "description"    : recruit.description,
                "minimum_salary" : recruit.minimum_salary,
                "maximum_salary" : recruit.maximum_salary,
                "deadline"       : recruit.deadline,
                "created_at"     : recruit.created_at,
                "updated_at"     : recruit.updated_at,
                "stacks"        : [ stack.name for stack in recruit.stacks.all() ]
            }
            for recruit in recruits
        ]
        return JsonResponse({"results": results}, status=200)

    @swagger_auto_schema (
        manual_parameters = [parameter_token],
        request_body = RecruitCreateBodySerializer, 
        responses = {
            "201": "SUCCESS",
            "400": "BAD_REQUEST",
            "401": "UNAUTHORIZED"
        },
        operation_id = "채용공고 생성",
        operation_description = "포지션, 설명, 기술스택, 근무타입(정규직/계약직), 경력타입(신입or경력or신입/경력), 채용인원, 모집마감일, 최소/최대 연봉을 body에 담아 보내주세요."
    )
    @admin_only
    def post(self, request):
        try:
            career_type_choices = {
                "신입": "N",
                "경력": "C",
                "신입/경력": "NC",
            }

            data           = json.loads(request.body)
            position       = data["position"]
            position_title = data["position_title"]
            description    = data["description"]
            stack_names    = data["stacks"]
            job_openings   = data["job_openings"]
            work_type      = data["work_type"]
            career_type    = data["career_type"] if data["career_type"] else "신입/경력"
            deadline       = data["deadline"]
            minimum_salary = data["minimum_salary"]
            maximum_salary = data["maximum_salary"]

            author = request.user.email

            if not (career_type in career_type_choices):
                return JsonResponse({"message": "BAD_REQUEST"}, status=400)

            stacks = []
            
            for stack_name in stack_names:
                s = hashlib.sha3_256()
                s.update(stack_name.encode())
                hash_id = s.hexdigest()

                object, is_created = Stack.objects.get_or_create(hash_id=hash_id, name=stack_name)
                stacks.append(object)

            
            recruit = Recruit.objects.create(
                position       = position,
                position_title = position_title,
                description    = description,
                work_type      = work_type,
                career_type    = career_type_choices[career_type],
                job_openings   = job_openings,
                author         = author,
                deadline       = deadline if deadline else "9999-12-31",
                minimum_salary = minimum_salary if minimum_salary else 0,
                maximum_salary = maximum_salary if maximum_salary else 0
            )
            recruit.stacks.add(*stacks)

            return JsonResponse({"message": "SUCCESS"}, status=201)

        except KeyError:
            return JsonResponse({"message": "KEY_ERROR"}, status=400)
        except TypeError:
            return JsonResponse({"message": "TYPE_ERROR"}, status=400)

class RecruitView(APIView):
    parameter_token = openapi.Parameter (
                                        "Authorization", 
                                        openapi.IN_HEADER, 
                                        description = "access_token", 
                                        type        = openapi.TYPE_STRING,
                                        default     = ADMIN_TOKEN
    )

    recruit_get_response = openapi.Response("result", RecruitSerializer)

    @swagger_auto_schema(
        responses = {
            "200": recruit_get_response,
            "404": "NOT_FOUND"
        },
        operation_id = "채용공고 상세 조회",
        operation_description = "특정 채용공고 정보를 조회합니다."
    )
    def get(self, request, recruit_id):
        try:
            recruit = Recruit.objects.prefetch_related('stacks').get(id=recruit_id)

            result = {
                "id"             : recruit.id,
                "position"       : recruit.position,
                "position_title" : recruit.position_title,
                "work_type"      : recruit.work_type,
                "career_type"    : recruit.get_career_type_display(),
                "author"         : recruit.author,
                "job_openings"   : recruit.job_openings,
                "description"    : recruit.description,
                "minimum_salary" : recruit.minimum_salary,
                "maximum_salary" : recruit.maximum_salary,
                "deadline"       : recruit.deadline,
                "created_at"     : recruit.created_at,
                "updated_at"     : recruit.updated_at,
                "stacks"         : [ stack.name for stack in recruit.stacks.all() ]
            }

            return JsonResponse({"result": result}, status=200)

        except Recruit.DoesNotExist:
            return JsonResponse({"message": "NOT_FOUND"}, status=404)

    @swagger_auto_schema (
        manual_parameters = [parameter_token],
        request_body = RecruitCreateBodySerializer, 
        responses = {
            "200": "SUCCESS",
            "400": "BAD_REQUEST",
            "401": "UNAUTHORIZED",
            "404": "NOT_FOUND"
        },
        operation_id = "채용공고 수정",
        operation_description = "포지션, 설명, 기술스택, 근무타입(정규직/계약직), 경력타입(신입or경력or신입/경력), 채용인원, 모집마감일, 최소/최대 연봉을 body에 담아 보내주세요."
    )
    @admin_only
    def patch(self, request, recruit_id):
        try:
            recruit = Recruit.objects.get(id=recruit_id)

            career_type_choices = {
                "신입": "N",
                "경력": "C",
                "신입/경력": "NC",
            }

            data           = json.loads(request.body)
            position       = data["position"]
            position_title = data["position_title"]
            description    = data["description"]
            stack_names    = data["stacks"]
            work_type      = data["work_type"]
            career_type    = data["career_type"] if data["career_type"] else "신입/경력"
            job_openings   = data["job_openings"]
            deadline       = data["deadline"]
            minimum_salary = data["minimum_salary"]
            maximum_salary = data["maximum_salary"]

            author = request.user.email

            if not (career_type in career_type_choices):
                return JsonResponse({"message": "BAD_REQUEST"}, status=400)

            stacks_to_add = []
            
            for stack_name in stack_names:
                s = hashlib.sha3_256()
                s.update(stack_name.encode())
                hash_id = s.hexdigest()

                object, is_created = Stack.objects.get_or_create(hash_id=hash_id, name=stack_name)
                stacks_to_add.append(object)

            recruit.position       = position
            recruit.position_title = position_title
            recruit.description    = description
            recruit.work_type      = work_type
            recruit.career_type    = career_type_choices[career_type]
            recruit.job_openings   = job_openings
            recruit.author         = author
            recruit.deadline       = deadline if deadline else "9999-12-31"
            recruit.minimum_salary = minimum_salary if minimum_salary else 0
            recruit.maximum_salary = maximum_salary if maximum_salary else 0
            recruit.save()

            items = RecruitStack.objects.select_related("stack").filter(recruit=recruit)
            
            stacks_to_remove = []

            for item in items:
                if not item.stack in stacks_to_add:
                    stacks_to_remove.append(item.stack)
            
            recruit.stacks.remove(*stacks_to_remove)
            recruit.stacks.add(*stacks_to_add)

            return JsonResponse({"message": "SUCCESS"}, status=200)

        except Recruit.DoesNotExist:
            return JsonResponse({"message": "NOT_FOUND"}, stauts=404)
        except TypeError:
            return JsonResponse({"message": "TYPE_ERROR"}, status=400)

    @swagger_auto_schema(
        manual_parameters = [parameter_token],
        responses = {
            "200": "SUCCESS",
            "401": "UNAUTHORIZED",
            "404": "NOT_FOUND"
        },
        operation_id = "채용공고 삭제",
        operation_description = "특정 채용공고를 삭제합니다."
    )
    @admin_only
    def delete(self, request, recruit_id):
        try: 
            recruit = Recruit.objects.get(id=recruit_id)
            recruit.delete()

            return JsonResponse({"meessage": "SUCCESS"}, status=200)

        except Recruit.DoesNotExist:
            return JsonResponse({"message": "NOT_FOUND"}, status=404)