from flask import jsonify


def res(msg="", data=None, code=200):
    return jsonify({
        "message": msg,
        "data": data if data is not None else []
    }), code
