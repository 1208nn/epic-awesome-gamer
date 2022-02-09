# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from typing import Optional

from selenium.common.exceptions import WebDriverException

from services.bricklayer import Bricklayer
from services.explorer import Explorer
from services.settings import logger
from services.utils import CoroutineSpeedup, ToolBox

SILENCE = True

bricklayer = Bricklayer(silence=SILENCE)
explorer = Explorer(silence=SILENCE)


class SpawnBooster(CoroutineSpeedup):
    """协程助推器 并发执行片段代码"""

    def __init__(
        self,
        docker,
        ctx_cookies,
        power: Optional[int] = None,
        debug: Optional[bool] = None,
    ):
        super().__init__(docker=docker, power=power)

        self.debug = False if debug is None else debug
        self.power = min(4, 4 if power is None else power)
        self.action_name = "SpawnBooster"

        self.ctx_cookies = ctx_cookies

    def control_driver(self, task, *args, **kwargs):
        url = task

        # 运行前置检查
        response = explorer.game_manager.is_my_game(
            ctx_cookies=self.ctx_cookies, page_link=url
        )

        # 启动 Bricklayer，获取免费游戏
        if response.get("status") is False:
            logger.debug(
                ToolBox.runtime_report(
                    motive="BUILD",
                    action_name=self.action_name,
                    message="🛒 正在为玩家领取免费游戏",
                    progress=f"[{self.progress()}]",
                    url=url,
                )
            )

            try:
                bricklayer.get_free_game(
                    page_link=url, ctx_cookies=self.ctx_cookies, refresh=False
                )
            except WebDriverException as error:
                if self.debug:
                    logger.exception(error)
                logger.error(
                    ToolBox.runtime_report(
                        motive="QUIT",
                        action_name="SpawnBooster",
                        message="未知错误",
                        progress=f"[{self.progress()}]",
                        url=url,
                    )
                )

    def killer(self):
        logger.success(
            ToolBox.runtime_report(
                motive="OVER", action_name=self.action_name, message="✔ 任务队列已清空"
            )
        )


def join(trace: bool = False):
    """
    科技改变生活，一键操作，将免费商城搬空！

    :param trace:
    :return:
    """
    logger.info(
        ToolBox.runtime_report(
            motive="STARTUP", action_name="ScaffoldGet", message="🔨 正在为玩家领取免费游戏"
        )
    )

    # [🔨] 刷新上下文身份令牌
    if not bricklayer.cookie_manager.refresh_ctx_cookies():
        return

    # [🔨] 读取有效的身份令牌
    ctx_cookies = bricklayer.cookie_manager.load_ctx_cookies()

    # [🔨] 缓存免费商城数据
    urls = explorer.game_manager.load_game_objs(only_url=True)
    if not urls:
        urls = explorer.discovery_free_games(ctx_cookies=ctx_cookies, cover=True)

    # [🔨] 启动 Bricklayer 搬空免费商店
    # 启动一轮协程任务，执行效率受限于本地网络带宽
    SpawnBooster(ctx_cookies=ctx_cookies, docker=urls, power=4, debug=trace).go()


def special(special_link: str):
    """
    领取指定游戏

    :param special_link: 游戏商城的 *中文* 本地化链接
    :return:
    """
    if not special_link.startswith("https://www.epicgames.com/store/zh-CN"):
        logger.critical(
            ToolBox.runtime_report(
                motive="STARTUP", action_name="ScaffoldGet", message="链接不合法"
            )
        )
        return
    logger.info(
        ToolBox.runtime_report(
            motive="STARTUP", action_name="ScaffoldGet", message="🎯 正在为玩家领取指定游戏"
        )
    )

    # [🔨] 刷新上下文身份令牌
    if not bricklayer.cookie_manager.refresh_ctx_cookies():
        return

    # [🔨] 读取有效的身份令牌
    ctx_cookies = bricklayer.cookie_manager.load_ctx_cookies()

    # [🔨] 启动 Bricklayer 领取指定游戏
    bricklayer.get_free_game(
        page_link=special_link, ctx_cookies=ctx_cookies, challenge=True
    )
