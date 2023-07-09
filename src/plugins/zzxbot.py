import json
import os
import time
from typing import Any

import httpx
from httpx import Response
from nonebot import on_command, on_request, on_notice
from nonebot.adapters.onebot.v11 import Event, GroupRequestEvent, GroupDecreaseNoticeEvent, \
    FriendRequestEvent, \
    Bot, GroupIncreaseNoticeEvent, Message
from nonebot.matcher import Matcher

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BOT_NAME = "ZzxBot"
BOT_WEBSITE = "https://cubewhy.eu.org"

BOT_DOC = f"""{BOT_NAME}
By LunarCN dev
获取更多信息请输入/help"""


class BotUtils(object):

    def __init__(self):
        object.__init__(self)

        self.config: dict = {}
        self.config_dir = os.path.join(BASE_DIR, "config")
        if not os.path.isdir(self.config_dir):
            os.makedirs(self.config_dir)

        self.config_json = os.path.join(self.config_dir, "config.json")
        self.load()

        self.init_bot()  # 初始化机器人

    def load(self):
        if not os.path.isfile(self.config_json):
            self.save()
        with open(self.config_json, "r") as f:
            self.config: dict = json.load(f)

    def save(self):
        with open(self.config_json, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def init_bot(self):
        if "bot" not in self.config:
            self.config["bot"] = {
                "admins": [],  # 管理员
                "notify-groups": []  # 通知群
            }
        if "modules" not in self.config:
            self.config["modules"] = {}
        self.save()

    def get_state(self, module_name: str) -> Any | None:
        if module_name in self.config["modules"]:
            return self.config["modules"][module_name]["state"]
        return None

    def set_state(self, module_name: str, state: bool):
        self.config["modules"][module_name]["state"] = state
        self.save()

    def init_module(self, module_name: str):
        self.config["modules"][module_name] = {"state": True}
        self.save()

    def init_value(self, module_name: str, key: str, default_value: Any = None):
        if key not in self.config["modules"][module_name] and default_value is not None:
            self.config["modules"][module_name][key] = default_value
            self.save()
        return self.config["modules"][module_name][key]

    def get_module(self, module_name: str) -> Any | str:
        if module_name in self.config["modules"]:
            return self.config["modules"][module_name]
        return None

    def get_admins(self) -> str:
        return self.config["bot"]["admins"]


class BlackList(object):
    def __init__(self):
        object.__init__(self)
        self.config: dict = {}
        self.config_dir = os.path.join(BASE_DIR, "config")
        self.bl_json = os.path.join(self.config_dir, "black-list.json")

        self.load()
        self.__init()

    def load(self):
        if not os.path.isfile(self.bl_json):
            self.save()
        with open(self.bl_json, "r") as f:
            self.config: dict = json.load(f)

    def save(self):
        with open(self.bl_json, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def __init(self):
        if "black-list" not in self.config:
            self.config["black-list"] = {}
            self.save()

    def get_black_list(self):
        return self.config["black-list"]

    def in_black_list(self, uid: str):
        return uid in self.config["black-list"]

    def add_user(self, uid: str, reason: str = "idk"):
        self.config["black-list"][uid] = {"reason": reason, "add-date": time.time()}
        self.save()

    def get_user(self, uid: str):
        return self.config["black-list"][uid]


async def get_user_name(bot: Bot, uid: str):
    """获取用户名"""
    return (await bot.get_stranger_info(user_id=int(uid), no_cache=True))["nickname"]


utils = BotUtils()
black_list = BlackList()


def check(module_id: str, event: Event, *, admin: bool = False):
    if not admin:
        return utils.get_state(module_id)
    return utils.get_state(module_id) and event.get_user_id() in utils.get_admins()


def is_admin(event: Event):
    return event.get_user_id() in utils.get_admins()


def parse_arg(arg_str: str) -> list:
    return arg_str.split(" ")[1:]


async def get(url: str) -> Response:
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        return r


async def post(url: str, params: dict) -> Response:
    async with httpx.AsyncClient() as client:
        r = await client.post(url, params=params)
        return r


@on_command("toggle", priority=1, block=False).handle()
async def on_handle(matcher: Matcher, event: Event):
    if not is_admin(event):
        matcher.stop_propagation()
    arg = parse_arg(event.get_plaintext())
    if len(arg) == 0:
        await matcher.finish("[Toggle] 参数错误 -> /toggle <moduleName: string>")
    module_name: str = arg[0]
    current_state: Any | bool = utils.get_state(module_name)
    if current_state is None:
        await matcher.finish(f"[Toggle] 模块 {module_name} 不存在")
    utils.set_state(module_name, not current_state)
    await matcher.finish(
        f"[Toggle] 模块{module_name}状态切换成功, 现在状态为{'启用' if utils.get_module(module_name) else '禁用'}")


@on_command("bot").handle()
async def on_handle(matcher: Matcher, event: Event):
    await matcher.finish(BOT_DOC)


@on_command("bl").handle()
async def on_handle(matcher: Matcher, event: Event):
    arg = parse_arg(event.get_plaintext())
    if len(arg) == 1:
        match arg[0]:
            case "add":
                await matcher.finish("[BlackList] 添加黑名单 -> /bl add <uid> [reason]")
            case "remove":
                await matcher.finish("[BlackList] 移除黑名单 -> /bl remove <uid>")
            case "get":
                await matcher.finish("[BlackList] 查询黑名单[不需要管理员权限] -> /bl get <uid>")
    elif len(arg) == 2 and arg[0] == "get":
        uid = arg[1]
        if black_list.in_black_list(uid):
            await matcher.finish(
                f"[BlackList] 黑名单查询结果\nUID: {uid}\nREASON: {black_list.get_user(uid)['reason']}")
        else:
            await matcher.finish(f"[BlackList] {uid} 不在黑名单内")
    elif len(arg) >= 2:
        if not is_admin(event):
            matcher.stop_propagation()
        sub1 = arg[0]
        match sub1:
            case "add":
                uid = arg[1]
                reason: str = "idk"
                if len(arg) >= 3:
                    reason = " ".join(arg[2:])
                black_list.add_user(uid, reason)
                await matcher.finish(
                    f"[BlackList] 成功{('修改 ' + uid + ' 的封禁原因') if black_list.in_black_list(uid) else ('添加 ' + uid + ' 到黑名单中')}")
            case "remove":
                uid = arg[1]
                if not black_list.in_black_list(uid):
                    await matcher.finish(f"[BlackList] UID{uid} 不存在于黑名单中")
                await matcher.finish(f"[BlackList] 成功解除{uid}的封禁")
    else:
        await matcher.finish("[BlackList] 错误的使用方法 -> /bl add|remove|get [sub-args]")


# Module AutoAccept

@on_request().handle()
async def on_handle(bot: Bot, matcher: Matcher, event: FriendRequestEvent):
    if not utils.get_state("auto-accept"):
        matcher.stop_propagation()
    raw: dict = json.loads(event.json())
    flag = raw["flag"]
    uid = event.get_user_id()
    await bot.set_friend_add_request(flag=flag, approve=not black_list.in_black_list(uid))


@on_request().handle()
async def on_handle(bot: Bot, matcher: Matcher, event: GroupRequestEvent):
    if not utils.get_state("auto-accept"):
        matcher.stop_propagation()
    group: str = str(event.group_id)
    user: str = event.get_user_id()
    raw: dict = json.loads(event.json())
    comment: str = raw["comment"]
    flag = raw["flag"]
    sub_type: str = raw["sub_type"]
    is_invite = "invitor_id" in raw

    if sub_type == "invite":
        await bot.set_group_add_request(flag=flag, sub_type=sub_type, approve=(user in utils.get_admins()),
                                        reason="You can't invite bot")
        await bot.send_private_msg(user_id=int(user),
                                   message="You attempted to invite the bot, but this bot doesn't allow invitations")
    elif sub_type == "add":
        if black_list.in_black_list(user) or (is_invite and black_list.in_black_list(str(raw["invitor_id"]))):
            await bot.set_group_add_request(flag=flag, sub_type=sub_type, approve=False, reason="QQ存在黑名单中")
        elif get_accept_type(group) == "accept":
            await bot.set_group_add_request(flag=flag, sub_type=sub_type, approve=True, reason="Accepted")
        elif get_accept_type(group) == "reject":
            await bot.set_group_add_request(flag=flag, sub_type=sub_type, approve=False, reason="禁止所有人加入")
        elif get_accept_type(group) == "include":
            target_text = get_group(group)["target"]
            await bot.set_group_add_request(flag=flag, sub_type=sub_type, approve=target_text in comment,
                                            reason="加群消息不包含目标文字")


def get_group(group_id: str) -> dict | None:
    groups: dict = utils.init_value("auto-accept", "groups")
    if group_id in groups:
        return groups[group_id]
    return None


def get_accept_type(group_id: str) -> None | str:
    return get_group(group_id)["type"]


utils.init_module("auto-accept")
utils.init_value("auto-accept", "groups", {})


# Module AutoAccept end

# Module AutoWelcome

@on_notice().handle()
async def on_handle_join(bot: Bot, matcher: Matcher, event: GroupIncreaseNoticeEvent):
    if not check("auto-welcome", event):
        matcher.stop_propagation()
    uid = event.get_user_id()
    gid = str(event.group_id)
    auto_kick: bool = utils.init_value("auto-welcome", "auto-kick")
    groups: dict = utils.init_value("auto-welcome", "groups")
    if gid not in groups:
        matcher.stop_propagation()
    if black_list.in_black_list(uid) and auto_kick:
        await bot.set_group_kick(group_id=int(gid), user_id=int(uid), reject_add_request=False)

    if gid not in groups:
        matcher.stop_propagation()
    message: str = groups[gid].replace("%name%", f"[CQ:at,qq={uid}] ")

    if event.get_user_id() == bot.self_id:
        await matcher.finish(
            f"[AutoWelcome] 我是{BOT_NAME}, 我可以替代Q群管家, 如果你要获得更好的群聊体验, 请把我设置成管理员并删除Q群管家")
    else:
        await matcher.finish(Message(message))


@on_notice().handle()
async def on_handle_left(bot: Bot, matcher: Matcher, event: GroupDecreaseNoticeEvent):
    if not check("auto-welcome", event):
        matcher.stop_propagation()
    leave_message: str = utils.init_value("auto-welcome", "leave-message")
    uid = event.get_user_id()

    user_name = get_user_name(bot, uid)
    message = leave_message.replace("%name%", f"{user_name} ({uid})")
    await matcher.finish(Message(message))


utils.init_module("auto-welcome")
utils.init_value("auto-welcome", "auto-kick", True)
utils.init_value("auto-welcome", "leave-message", "%name% left")
utils.init_value("auto-welcome", "groups", {})


# Module AutoWelcome end

# Module OF cape start
async def get_exact_minecraft_name(username: str) -> None | str:
    """获取有大小写的Minecraft用户名称"""
    if len(username) > 17:
        r = await get("https://sessionserver.mojang.com/session/minecraft/profile/")
        username = r
    r = await get("https://api.mojang.com/users/profiles/minecraft/" + username)
    if r.status_code == 200:
        return r.json()["name"]
    return None


async def get_of_cape(username: str, proxy="http://s.optifine.net/capes") -> dict:
    username = await get_exact_minecraft_name(username)
    cape_image = proxy + "/{}.png".format(username)
    r = await get(cape_image)
    if r.status_code != 200:
        return {"state": False, "username": username}
    cape_api = "https://www.optifine.net/banners"
    r = await post(cape_api, {"username": username})
    if proxy == "http://s.optifine.net/capes":
        cape_url = r.next_request.url if r.next_request else None
    else:
        cape_url = cape_image
    if cape_url == cape_api:
        return {"state": True, "cape": None, "image": cape_image, "username": username}
    return {"state": True, "cape": cape_url, "image": cape_image, "username": username}


@on_command("ofcape").handle()
async def on_handle(matcher: Matcher, event: Event):
    if not utils.get_state("ofcape"):
        matcher.stop_propagation()
    arg = parse_arg(event.get_plaintext())
    if len(arg) == 0:
        await matcher.finish("[OF Cape] 获取玩家OF披风 -> /ofcape <playerUuid|playerUserName> [proxy]")
    elif len(arg) == 1:
        username = arg[0]
        of = await get_of_cape(username)
        if of["state"]:
            await matcher.finish(
                Message("[OF Cape] Cape of {}\nURL: {}\n[CQ:image,file={}]".format(of["username"], of["cape"] if of[
                    "cape"] else "Default cape", of["image"])))
        else:
            await matcher.finish("[OF Cape] 玩家{}没有披风".format(of["username"]))
    elif len(arg) == 2:
        username = arg[0]
        proxy = arg[1]
        of = await get_of_cape(username, proxy)
        if of["state"]:
            await matcher.finish(
                Message("[OF Cape] Cape of {}\nURL: {} (On proxy server: {})\n[CQ:image,file={}]".format(of["username"],
                                                                                                         of["cape"] if
                                                                                                         of[
                                                                                                             "cape"] else "Default cape",
                                                                                                         proxy,
                                                                                                         of["image"])))
        else:
            await matcher.finish("[OF Cape] 玩家{}没有披风\nUse proxy: {}".format(of["username"], proxy))


utils.init_module("ofcape")
# Module OF cape end
