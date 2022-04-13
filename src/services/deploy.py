# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import apprise
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from gevent.queue import Queue

from services.bricklayer import Bricklayer
from services.bricklayer import UnrealClaimer
from services.explorer import Explorer
from services.settings import logger, MESSAGE_PUSHER_SETTINGS, PLAYER
from services.utils import ToolBox, get_challenge_ctx


class ClaimerScheduler:
    """系统任务调度器"""

    def __init__(self, silence: Optional[bool] = None, unreal: Optional[bool] = False):
        self.action_name = "AwesomeScheduler"
        self.end_date = datetime.now(pytz.timezone("Asia/Shanghai")) + timedelta(days=180)
        self.silence = silence
        self.unreal = unreal

        # 服务注册
        self.scheduler = BlockingScheduler()
        self.logger = logger

    def deploy_on_vps(self):
        """部署最佳实践的 VPS 定时任务"""

        # [⏰] 北京时间每周五凌晨 4 点的 两个任意时刻 执行任务
        jitter_minute = [random.randint(10, 20), random.randint(35, 57)]

        # [⚔] 首发任务用于主动认领，备用方案用于非轮询审核
        self.scheduler.add_job(
            func=self.job_loop_claim,
            trigger=CronTrigger(
                day_of_week="fri",
                hour="4",
                minute=f"{jitter_minute[0]},{jitter_minute[-1]}",
                second="30",
                timezone="Asia/Shanghai",
                # 必须使用 `end_date` 续订生产环境 定时重启
                end_date=self.end_date,
                # 必须使用 `jitter` 弥散任务发起时间
                jitter=15,
            ),
            name="loop_claim",
        )

        self.logger.debug(
            ToolBox.runtime_report(
                motive="JOB",
                action_name=self.action_name,
                message=f"任务将在北京时间每周五 04:{jitter_minute[0]} "
                f"以及 04:{jitter_minute[-1]} 执行。",
                end_date=str(self.end_date),
            )
        )

        # [⚔] Gracefully run scheduler.`
        try:
            self.scheduler.start()
        except KeyboardInterrupt:
            self.scheduler.shutdown(wait=False)
            self.logger.debug(
                ToolBox.runtime_report(
                    motive="EXITS",
                    action_name=self.action_name,
                    message="Received keyboard interrupt signal.",
                )
            )

    def deploy_jobs(self, platform: Optional[str] = None):
        """
        部署系统任务

        :param platform: within [vps serverless qing-long]
        :return:
        """
        platform = "vps" if platform is None else platform
        if platform not in ["vps", "serverless", "qing-long"]:
            raise NotImplementedError

        self.logger.debug(
            ToolBox.runtime_report(
                motive="JOB",
                action_name=self.action_name,
                message="部署任务调度器",
                platform=platform.upper(),
            )
        )

        # [⚔] Distribute common state machine patterns
        if platform == "vps":
            self.deploy_on_vps()
        elif platform == "serverless":
            raise NotImplementedError
        elif platform == "qing-long":
            return self.job_loop_claim()

    def job_loop_claim(self):
        """wrap function for claimer instance"""
        if not self.unreal:
            with ClaimerInstance(silence=self.silence) as claimer:
                claimer.just_do_it()
        else:
            with UnrealClaimerInstance(silence=self.silence) as claimer:
                claimer.just_do_it()


class ClaimerInstance:
    """单步子任务 认领周免游戏"""

    def __init__(self, silence: bool, log_ignore: Optional[bool] = False, _auth_str=None):
        """

        :param silence:
        :param log_ignore: 过滤掉已在库的资源实体的推送信息。
        """
        self.action_name = "ClaimerInstance"
        self.silence = silence
        self.logger = logger
        self.log_ignore = log_ignore

        # 服务注册
        auth_str = "games" if _auth_str is None else _auth_str
        self.bricklayer = Bricklayer(silence=silence, auth_str=auth_str)
        self.explorer = Explorer(silence=silence)

        # 任务队列 按顺缓存周免游戏及其免费附加内容的认领任务
        self.task_queue = Queue()
        # 消息队列 按序缓存认领任务的执行状态
        self.message_queue = Queue()
        # 内联数据容器 编排推送模版
        self.inline_docker = []

    def __enter__(self):
        # 集成统一的驱动上下文，减少内存占用
        self.challenger = get_challenge_ctx(silence=self.silence)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 消息推送
        self._pusher_wrapper()

        # 缓存卸载
        if hasattr(self, "challenger"):
            self.challenger.quit()

    def _pusher_wrapper(self):
        while not self.message_queue.empty():
            context = self.message_queue.get()
            # 过滤已在库的游戏资源的推送数据
            if (
                self.log_ignore is True
                and context["status"] == self.bricklayer.assert_.GAME_OK
            ):
                continue
            self.inline_docker.append(context)

        # 在 `ignore` 模式下当所有资源实体都已在库时不推送消息
        if self.inline_docker:
            self._push(inline_docker=self.inline_docker)
        # 在 `ignore` 模式下追加 DEBUG 标签日志
        elif self.log_ignore:
            self.logger.debug(
                ToolBox.runtime_report(
                    motive="Notify",
                    action_name=self.action_name,
                    message="忽略已在库的资源实体推送信息",
                    ignore=self.log_ignore,
                )
            )

    def _push(self, inline_docker: list, pusher_settings: Optional[dict] = None):
        """
        推送追踪日志

        :param inline_docker:
        :param pusher_settings:
        :return:
        """
        # -------------------------
        # [♻]参数过滤
        # -------------------------
        if pusher_settings is None:
            pusher_settings = MESSAGE_PUSHER_SETTINGS
        if not pusher_settings["enable"]:
            return
        # -------------------------
        # [📧]消息推送
        # -------------------------
        _inline_textbox = ["<周免游戏>".center(20, "=")]
        if not inline_docker:
            _inline_textbox += [f"[{ToolBox.date_format_now()}] 🛴 暂无待认领的周免游戏"]
        else:
            _game_textbox = []
            _dlc_textbox = []
            for game_obj in inline_docker:
                if not game_obj.get("dlc"):
                    _game_textbox.append(f"[{game_obj['status']}] {game_obj['name']}")
                else:
                    _dlc_textbox.append(f"[{game_obj['status']}] {game_obj['name']}")
            _inline_textbox.extend(_game_textbox)
            if _dlc_textbox:
                _inline_textbox += ["<附加内容>".center(20, "=")]
                _inline_textbox.extend(_dlc_textbox)
        _inline_textbox += [
            "<操作统计>".center(20, "="),
            f"Player: {PLAYER}",
            f"Total: {inline_docker.__len__()}",
        ]

        # 注册 Apprise 消息推送框架
        active_pusher = pusher_settings["pusher"]
        surprise = apprise.Apprise()
        for server in active_pusher.values():
            surprise.add(server)

        # 发送模版消息
        surprise.notify(body="\n".join(_inline_textbox), title="EpicAwesomeGamer 运行报告")

        self.logger.success(
            ToolBox.runtime_report(
                motive="Notify",
                action_name=self.action_name,
                message="消息推送完毕",
                active_pusher=[i[0] for i in active_pusher.items() if i[-1]],
            )
        )

    def promotions_filter(
        self, promotions: Optional[Dict[str, Any]], ctx_cookies: List[dict]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        促销实体过滤器

        1. 判断游戏本体是否在库
        2. 判断是否存在免费附加内容
        3. 识别并弹出已在库资源
        4. 返回待认领的实体资源
        :param promotions:
        :param ctx_cookies:
        :return:
        """

        def in_library(page_link: str, name: str):
            response = self.explorer.game_manager.is_my_game(
                ctx_cookies=ctx_cookies, page_link=page_link
            )
            # 资源待认领
            if not response["status"] and response["assert"] != "AssertObjectNotFound":
                self.logger.debug(
                    ToolBox.runtime_report(
                        motive="STARTUP",
                        action_name="ScaffoldClaim",
                        message="🍜 正在为玩家领取周免游戏",
                        game=f"『{name}』",
                    )
                )
                return False
            self.logger.info(
                ToolBox.runtime_report(
                    motive="GET",
                    action_name=self.action_name,
                    message="🛴 资源已在库",
                    game=f"『{name}』",
                )
            )
            return True

        if not isinstance(promotions, dict) or not promotions["urls"]:
            return promotions

        # 过滤资源实体
        pending_objs = []
        for url in promotions["urls"]:
            # 标记已在库游戏本体
            job_name = promotions[url]
            pending_objs.append(
                {"url": url, "name": job_name, "in_library": in_library(url, job_name)}
            )

            # 识别免费附加内容
            dlc_details = self.bricklayer.get_free_dlc_details(
                ctx_url=url, ctx_cookies=ctx_cookies
            )

            # 标记已在库的免费附加内容
            for dlc in dlc_details:
                dlc.update({"in_library": in_library(dlc["url"], dlc["name"])})
                pending_objs.append(dlc)

        return pending_objs

    def just_do_it(self):
        """单步子任务 认领周免游戏"""
        # 检查并更新身份令牌
        if self.bricklayer.cookie_manager.refresh_ctx_cookies(
            _ctx_session=self.challenger
        ):
            # 读取有效的身份令牌
            ctx_cookies = self.bricklayer.cookie_manager.load_ctx_cookies()

            # 扫描商城促销活动，返回“0折”商品的名称与商城链接
            promotions = self.explorer.get_promotions(ctx_cookies)

            # 资源聚合过滤 从顶级接口剔除已在库资源
            game_objs = self.promotions_filter(promotions, ctx_cookies)

            # 启动任务队列
            for game in game_objs:
                if game["in_library"]:
                    result = self.bricklayer.assert_.GAME_OK
                else:
                    result = self.bricklayer.get_free_resources(
                        page_link=game["url"],
                        ctx_cookies=ctx_cookies,
                        ctx_session=self.challenger,
                    )
                _runtime = {
                    "status": result,
                    "name": game["name"],
                    "dlc": game.get("dlc", False),
                }
                self.message_queue.put_nowait(_runtime)


class UnrealClaimerInstance(ClaimerInstance):
    """虚幻商城月供砖家"""

    def __init__(self, silence: bool, log_ignore: Optional[bool] = False):
        super().__init__(silence=silence, log_ignore=log_ignore)

        self.bricklayer = UnrealClaimer(silence=silence)

    def just_do_it(self):
        """虚幻商城月供砖家"""
        # 检查并更新身份令牌
        if self.bricklayer.cookie_manager.refresh_ctx_cookies(
            _ctx_session=self.challenger
        ):
            # 读取有效的身份令牌
            ctx_cookies = self.bricklayer.cookie_manager.load_ctx_cookies()

            # 释放 Claimer 认领免费内容
            self.bricklayer.get_free_resource(
                ctx=self.challenger, ctx_cookies=ctx_cookies
            )

            # 检查运行结果
            details = self.bricklayer.get_claimer_response(ctx_cookies)
            for detail in details:
                self.message_queue.put_nowait(detail)
