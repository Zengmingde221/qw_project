# -*- coding: utf-8 -*-
"""
Flask 入门骨架 —— 单文件 app.py
包含：
    * GET /hello、GET /health —— 基础 GET 路由案例
    * GET /  —— 企业微信回调验证接口（当请求带 msg_signature/timestamp/nonce/echostr 参数时）

启动方式：
    .venv/Scripts/python app.py

企业微信回调验证流程（1 秒内完成）：
    1. 对收到的请求做 Urldecode 处理
    2. 用 msg_signature 校验请求合法性
    3. 解密 echostr 得到明文消息内容
    4. 原样返回明文（不加引号、不带 BOM、不带换行符）
"""
import logging
import os
import sys
from urllib.parse import unquote

from flask import Flask, request, jsonify, Response

# ---------- 日志配置 ----------
# 等级可用环境变量 LOG_LEVEL 覆盖，如 LOG_LEVEL=DEBUG 启动可看到更详细的调试日志
logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("qw_project")

# ---------- 企业微信 SDK 导入 ----------
# 将 weworkapi/callback_python3 加入模块搜索路径（SDK 通过 sys.path.append 引用，非 pip 包）
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(_BASE_DIR, "weworkapi", "callback_python3"))

from WXBizMsgCrypt import WXBizMsgCrypt          # noqa: E402

# ---------- 企业微信配置（TODO: 填你在企业微信后台"接收消息服务器配置"中的值） ----------
# 与后台配置的 Token 一致
TOKEN = "CULycBNSMQ6HnvBvOx"
# 与后台配置的 EncodingAESKey 一致（43 位字符，注意保存后不可修改）
ENCODING_AES_KEY = "x2FSrUbaCvRYi3qO0CMDPgC2pQ9i27ZJN7DBJDvNP92"
# 企业微信 CorpID（企业 ID）
CORP_ID = "wwbdfa8ada74ddffd6"

# 创建 Flask 应用实例
app = Flask(__name__)


def _parse_query_string(raw_query: bytes) -> dict:
    """
    手动解析原始 query_string 并做 Urldecode。

    用 urllib.parse.unquote 解码（不会把 '+' 转成空格），避免 Flask 默认
    form-urlencoded 解析把 echostr 里的 base64 '+' 字符变成空格而损坏密文。
    """
    logger.debug("解析原始 query_string: %r", raw_query)
    params = {}
    if not raw_query:
        logger.debug("query_string 为空，返回空参数字典")
        return params
    for pair in raw_query.decode("utf-8").split("&"):
        if not pair:
            continue
        key, _, value = pair.partition("=")
        params[unquote(key)] = unquote(value)
    logger.debug("解析结果 %d 个参数: %s", len(params), params)
    return params


# ============ 企业微信回调验证（GET） ============
@app.route("/", methods=["GET"])
def index():
    """根路径：企业微信回调验证接口；完全无参数时显示欢迎信息。"""
    logger.info("收到 GET / 请求，client=%s，原始 query_string=%r",
                request.remote_addr, request.query_string)
    params = _parse_query_string(request.query_string)

    # 无任何查询参数：按普通欢迎页处理
    if not params:
        logger.info("无查询参数，返回欢迎页")
        return "Welcome to the Flask app! Try /hello?name=xxx or /health"

    # 回调参数齐全：进入验证流程
    required = ("msg_signature", "timestamp", "nonce", "echostr")
    if all(k in params for k in required):
        logger.info("回调 4 参数齐全（msg_signature=%s timestamp=%s nonce=%s），进入 URL 验证",
                    params["msg_signature"], params["timestamp"], params["nonce"])
        return _verify_url(
            params["msg_signature"],
            params["timestamp"],
            params["nonce"],
            params["echostr"],
        )

    # 带了回调参数但不完整：按无效请求处理
    logger.warning("带了查询参数但缺少回调必需参数（现有参数: %s），返回 400",
                   sorted(params.keys()))
    return Response("missing required params", status=400, mimetype="text/plain")


def _verify_url(msg_signature, timestamp, nonce, echostr):
    """
    企业微信 URL 验证：
    1. 签名校验（msg_signature 结合 token、timestamp、nonce、加密消息体）
    2. 解密 echostr，得到明文消息内容
    返回明文消息内容，1 秒内原样返回（不加引号、不带 BOM、不带换行符）。
    """
    logger.info("===== 进入企业微信 URL 验证 =====")
    logger.info("参数: msg_signature=%r, timestamp=%r, nonce=%r, echostr长度=%d",
                msg_signature, timestamp, nonce, len(echostr))

    # 配置仍是占位符：直接提示，避免 SDK 构造时抛异常变成 500
    if any("your_" in v for v in (TOKEN, ENCODING_AES_KEY, CORP_ID)):
        logger.error("配置仍是占位符（TOKEN=%s ENCODING_AES_KEY=%s CORP_ID=%s），拒绝验证",
                     TOKEN, ENCODING_AES_KEY, CORP_ID)
        return Response(
            "callback not configured: please fill real TOKEN / ENCODING_AES_KEY / CORP_ID in app.py",
            status=400,
            mimetype="text/plain",
        )

    # 初始化 SDK 加密组件（Token / EncodingAESKey / CorpID 均来自配置）
    try:
        wxcpt = WXBizMsgCrypt(TOKEN, ENCODING_AES_KEY, CORP_ID)
        logger.info("WXBizMsgCrypt 初始化成功")
    except Exception as e:
        # 配置格式不合法（如 EncodingAESKey 非 32 字节 base64）时 SDK 构造即抛异常
        logger.exception("WXBizMsgCrypt 初始化失败（配置格式不合法）: %s", e)
        return Response(
            "callback config error: %s" % e, status=400, mimetype="text/plain"
        )

    # 第 1 步：签名校验（用 token/timestamp/nonce/密文 计算签名并比对 msg_signature）
    # 第 2 步：校验通过后解密 echostr，得到明文
    ret, reply_echostr = wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
    logger.info("VerifyURL 返回: ret=%s, reply_echostr=%r", ret, reply_echostr)

    if ret != 0:
        # 校验/解密失败，企业微信会视为验证不通过
        logger.warning("签名校验或解密失败，ret=%d（企业微信将视为验证不通过）", ret)
        return Response("verify failed (ret=%d)" % ret, status=400, mimetype="text/plain")

    # 解密结果可能是 bytes，转成 utf-8 文本；Flask 不会添加 BOM 或尾随换行
    if isinstance(reply_echostr, bytes):
        reply_echostr = reply_echostr.decode("utf-8")
    logger.info("验证通过，明文=[%s]（长度 %d），原样返回", reply_echostr, len(reply_echostr))
    return Response(reply_echostr, mimetype="text/plain")


# ============ 基础 GET 路由案例 ============
@app.route("/hello", methods=["GET"])
def hello():
    """GET + 查询参数：演示 request.args.get() 读取 URL 上的 ?name=xxx，带默认值兜底。"""
    name = request.args.get("name", "World")
    logger.info("收到 GET /hello 请求，client=%s，name=%r", request.remote_addr, name)
    return "Hello, %s!" % name


@app.route("/health", methods=["GET"])
def health():
    """GET + JSON：健康检查接口，返回结构化状态。"""
    logger.info("收到 GET /health 健康检查请求，client=%s", request.remote_addr)
    return jsonify({
        "status": "ok",
        "app": "qw_project",
        "message": "Flask service is running",
    })


if __name__ == "__main__":
    # debug=True 便于开发调试（改代码自动重载、出错显示详情），生产环境务必关闭
    app.run(host="0.0.0.0", port=5000, debug=True)
