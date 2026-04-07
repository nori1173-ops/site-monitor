import json

from api.helpers.response import success_response, error_response


class TestSuccessResponse:
    """成功レスポンスのテスト"""

    def test_default_status_code(self):
        resp = success_response({"key": "value"})
        assert resp["statusCode"] == 200

    def test_custom_status_code(self):
        resp = success_response({"id": "123"}, status_code=201)
        assert resp["statusCode"] == 201

    def test_body_structure(self):
        resp = success_response({"key": "value"})
        body = json.loads(resp["body"])
        assert body["success"] is True
        assert body["data"] == {"key": "value"}
        assert body["error"] is None

    def test_cors_headers(self):
        resp = success_response({})
        assert resp["headers"]["Content-Type"] == "application/json"
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
        assert "Access-Control-Allow-Headers" in resp["headers"]

    def test_none_data(self):
        resp = success_response(None)
        body = json.loads(resp["body"])
        assert body["data"] is None

    def test_list_data(self):
        resp = success_response([1, 2, 3])
        body = json.loads(resp["body"])
        assert body["data"] == [1, 2, 3]


class TestErrorResponse:
    """エラーレスポンスのテスト"""

    def test_default_status_code(self):
        resp = error_response("Bad request")
        assert resp["statusCode"] == 400

    def test_custom_status_code(self):
        resp = error_response("Not found", status_code=404)
        assert resp["statusCode"] == 404

    def test_body_structure(self):
        resp = error_response("Something went wrong")
        body = json.loads(resp["body"])
        assert body["success"] is False
        assert body["data"] is None
        assert body["error"] == "Something went wrong"

    def test_cors_headers(self):
        resp = error_response("error")
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
