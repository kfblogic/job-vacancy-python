import json
from flask import Response

class ResponseHelper:
    @staticmethod
    def success_response(message, data):
        response = {
            'status': 'success',
            'message': message,
            'data': data
        }
        return Response(
            json.dumps(response, indent=4),
            status=200,
            mimetype='application/json'
        )

    @staticmethod
    def failure_response(message):
        response = {
            'status': 'failed',
            'message': message
        }
        return Response(
            json.dumps(response, indent=4),
            status=500,
            mimetype='application/json'
        )
