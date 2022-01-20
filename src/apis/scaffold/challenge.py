# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from services.bricklayer import Bricklayer
from services.bricklayer.exceptions import SurpriseExit
from services.settings import PATH_USR_COOKIES, logger
from services.utils import ToolBox

bricklayer = Bricklayer()


def run():
    """
    更新身份令牌

    :return:
    """

    """
    [🌀] 激活人机挑战
    _______________
    """
    logger.debug(ToolBox.runtime_report(
        motive="BUILD",
        action_name="ChallengeRunner",
        message="正在激活人机挑战..."
    ))
    bricklayer.cookie_manager.refresh_ctx_cookies(verify=True)

    """
    [🌀] 读取新的身份令牌
    _______________
    """
    ctx_cookies = bricklayer.cookie_manager.load_ctx_cookies()

    """
    [🌀] 保存用户令牌
    _______________
    """
    with open(PATH_USR_COOKIES, "w", encoding="utf8") as f:
        f.write(ToolBox.transfer_cookies(ctx_cookies))
    logger.success(ToolBox.runtime_report(
        motive="GET",
        action_name="ChallengeRunner",
        message="用户饼干已到货。",
        path=PATH_USR_COOKIES
    ))

    """
    [🌀] 优雅离场
    _______________
    脑洞大开的作者想挑战一下 Python 自带的垃圾回收机制，
    决定以一种极其垂直的方式结束系统任务。
    """
    raise SurpriseExit("优雅离场")
