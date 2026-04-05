import lark_oapi as lark


def do_p2_im_chat_access_event_bot_p2p_chat_entered_v1(
    data: lark.im.v1.P2ImChatAccessEventBotP2pChatEnteredV1,
) -> None:
    print(
        f"[ do_p2_im_chat_access_event_bot_p2p_chat_entered_v1 access ], data: {lark.JSON.marshal(data, indent=4)}"
    )


# 注册事件 Register event
event_handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(
        do_p2_im_chat_access_event_bot_p2p_chat_entered_v1
    )
    .build()
)


def main():
    # 构建 client Build client
    cli = lark.ws.Client(
        "APP_ID",
        "APP_SECRET",
        event_handler=event_handler,
        log_level=lark.LogLevel.DEBUG,
    )
    # 建立长连接 Establish persistent connection
    cli.start()


if __name__ == "__main__":
    main()
