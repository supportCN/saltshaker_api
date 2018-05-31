# -*- coding:utf-8 -*-
from flask_restful import Resource, reqparse, request
from flask import g
from common.log import loggers
from common.audit_log import audit_log
from common.db import DB
from common.utility import uuid_prefix
from common.sso import access_required
import json
from common.const import role_dict


logger = loggers()

parser = reqparse.RequestParser()
parser.add_argument("product_id", type=str, required=True, trim=True)
parser.add_argument("name", type=str, required=True, trim=True)
parser.add_argument("description", type=str, required=True, trim=True)
parser.add_argument("concurrent", type=int, default=0, trim=True)
parser.add_argument("period", type=str, default="once", trim=True)
parser.add_argument("time", type=str, default="now", trim=True)
parser.add_argument("date", type=str, default="now", trim=True)
parser.add_argument("cron", type=str, default="", trim=True)
parser.add_argument("type", type=str, default="", trim=True)
parser.add_argument("sls", type=str, default="", trim=True)
parser.add_argument("shell", type=str, default="", trim=True)
parser.add_argument("module", type=str, default="", trim=True)

parser.add_argument("target", type=str, required=True, action="append")


class Period(Resource):
    @access_required(role_dict["common_user"])
    def get(self, period_id):
        db = DB()
        status, result = db.select_by_id("period_task", period_id)
        db.close_mysql()
        if status is True:
            if result:
                return {"data": result, "status": True, "message": ""}, 200
            else:
                return {"status": False, "message": "%s does not exist" % period_id}, 404
        else:
            return {"status": False, "message": result}, 500

    @access_required(role_dict["common_user"])
    def delete(self, period_id):
        user = g.user_info["username"]
        db = DB()
        status, result = db.delete_by_id("period_task", period_id)
        db.close_mysql()
        if status is not True:
            logger.error("Delete period_task error: %s" % result)
            return {"status": False, "message": result}, 500
        if result is 0:
            return {"status": False, "message": "%s does not exist" % period_id}, 404
        audit_log(user, period_id, "", "period_task", "delete")
        return {"status": True, "message": ""}, 200

    @access_required(role_dict["common_user"])
    def put(self, period_id):
        user = g.user_info["username"]
        args = parser.parse_args()
        args["id"] = period_id
        period_task = args
        db = DB()
        # 判断是否存在
        select_status, select_result = db.select_by_id("period_task", period_id)
        if select_status is not True:
            db.close_mysql()
            logger.error("Modify period_task error: %s" % select_result)
            return {"status": False, "message": select_result}, 500
        if not select_result:
            db.close_mysql()
            return {"status": False, "message": "%s does not exist" % period_id}, 404
        # 判断名字否已经存在
        status, result = db.select("period_task", "where data -> '$.name'='%s' and data -> '$.product_id'='%s'"
                                   % (args["name"], args["product_id"]))
        if status is True and result:
            if period_id != result[0].get("id"):
                db.close_mysql()
                return {"status": False, "message": "The period_task name already exists"}, 200
        status, result = db.update_by_id("period_task", json.dumps(period_task, ensure_ascii=False), period_id)
        db.close_mysql()
        if status is not True:
            logger.error("Modify period_task error: %s" % result)
            return {"status": False, "message": result}, 500
        audit_log(user, period_id, "", "period_task", "edit")
        return {"status": True, "message": ""}, 200


class PeriodList(Resource):
    @access_required(role_dict["common_user"])
    def get(self):
        product_id = request.args.get("product_id")
        db = DB()
        task = []
        status, result = db.select("period_task", "where data -> '$.product_id'='%s'" % product_id)
        if status is True:
            for period in result:
                target = []
                for group_id in period.get("target"):
                    group_status, group_result = db.select_by_id("groups", group_id)
                    if group_status is True:
                        target.append({"id": group_id, "name": group_result.get("name")})
                period["target"] = target
                task.append(period)
            db.close_mysql()
            return {"data": task, "status": True, "message": ""}, 200
        else:
            return {"status": False, "message": task}, 500

    @access_required(role_dict["common_user"])
    def post(self):
        args = parser.parse_args()
        args["id"] = uuid_prefix("t")
        user = g.user_info["username"]
        period_task = args
        db = DB()
        status, result = db.select("period_task", "where data -> '$.name'='%s' and data -> '$.product_id'='%s'"
                                   % (args["name"], args["product_id"]))
        if status is True:
            if len(result) == 0:
                insert_status, insert_result = db.insert("period_task", json.dumps(period_task, ensure_ascii=False))
                db.close_mysql()
                if insert_status is not True:
                    logger.error("Add period_task error: %s" % insert_result)
                    return {"status": False, "message": insert_result}, 500
                audit_log(user, args["id"], "", "period_task", "add")
                return {"status": True, "message": ""}, 201
            else:
                db.close_mysql()
                return {"status": False, "message": "The period_task name already exists"}, 200
        else:
            db.close_mysql()
            logger.error("Select period_task name error: %s" % result)
            return {"status": False, "message": result}, 500