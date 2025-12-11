from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class ResultsPageNumberPagination(PageNumberPagination):
    page_size_query_param = "page_size"
    page_query_param = "page"

    def get_results(self, data):
        return data

    def get_paginated_response(self, data):
        return Response(self.get_results(data))
