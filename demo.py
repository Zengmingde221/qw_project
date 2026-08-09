# -*- coding: utf-8 -*-
"""
企业微信 API 使用示例（基于 weworkapi 官方库，已导入到本项目的 weworkapi/ 目录）

用法：
    1. 填写下面的 CORP_ID / AGENT_ID / APP_SECRET（在企业微信管理后台获取）
    2. python demo.py
"""
import sys
import os

# 把官方库的相关目录加入模块搜索路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "weworkapi"))
sys.path.append(os.path.join(BASE_DIR, "weworkapi", "api", "src"))
sys.path.append(os.path.join(BASE_DIR, "weworkapi", "callback_python3"))
sys.path.append(os.path.join(BASE_DIR, "weworkapi", "callback_json_python3"))

from CorpApi import CorpApi, CORP_API_TYPE          # noqa: E402
from AbstractApi import ApiException                # noqa: E402

# TODO: 填入你在企业微信管理后台的配置
CORP_ID = "your_corpid"
AGENT_ID = "your_agentid"
APP_SECRET = "your_app_secret"


def main():
    # 全局只实例化一次，库内部会自动缓存/刷新 access_token
    api = CorpApi(CORP_ID, APP_SECRET)

    try:
        # 例：获取部门列表
        response = api.httpCall(CORP_API_TYPE["DEPARTMENT_LIST"], {})
        print("部门列表:", response)

        # 例：给某用户发一条文本消息
        # response = api.httpCall(CORP_API_TYPE["MESSAGE_SEND"], {
        #     "touser": "zhangsan",
        #     "agentid": int(AGENT_ID),
        #     "msgtype": "text",
        #     "text": {"content": "hello"},
        #     "safe": 0,
        # })
        # print("发送结果:", response)
    except ApiException as e:
        print("接口调用失败: errCode=%s errMsg=%s" % (e.errCode, e.errMsg))


if __name__ == "__main__":
    main()
