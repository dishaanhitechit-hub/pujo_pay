from flask import jsonify


def success(data=None, message="success", status=200):
    body = {"status": "success", "message": message}
    if data is not None:
        body["data"] = data
    return jsonify(body), status


def error(message="error", status=400, errors=None):
    body = {"status": "error", "message": message}
    if errors:
        body["errors"] = errors
    return jsonify(body), status
