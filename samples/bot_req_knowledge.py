import json

import lark_oapi as lark
from lark_oapi.api.wiki.v2 import *
from config import load_config
import requests

def get_tenant_token(app_id, app_secret):
    # 请求地址
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
    post_data = {"app_id": app_id,
                "app_secret": app_secret}
    r = requests.post(url, data=post_data)
    return r.json()["tenant_access_token"]

# SDK 使用说明: https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/server-side-sdk/python--sdk/preparations-before-development
# 以下示例代码默认根据文档示例值填充，如果存在代码问题，请在 API 调试台填上相关必要参数后再复制代码使用
def main():
    # 创建client
    # 使用 user_access_token 需开启 token 配置, 并在 request_option 中配置 token
    config = load_config("code.bot.yaml")
    APP_ID = config.app_id
    APP_SECRET = config.app_secret
    client = lark.Client.builder() \
        .app_id(APP_ID) \
        .app_secret(APP_SECRET) \
        .log_level(lark.LogLevel.DEBUG) \
        .build()

    # 构造请求对象
    request: ListSpaceRequest = ListSpaceRequest.builder() \
        .page_size(20) \
        .build()

    # access token
    # 发起请求
    option = lark.RequestOption.builder().app_access_token(
        tat).build()
    response: ListSpaceResponse = client.wiki.v2.space.list(request, option)

    # 处理失败返回
    if not response.success():
        lark.logger.error(
            f"client.wiki.v2.space.list failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}")
        return

    # 处理业务结果
    lark.logger.info(lark.JSON.marshal(response.data, indent=4))


if __name__ == "__main__":
    main()
