import asyncio
import base64
import json
import os
import re
import time
from typing import Any

import httpx
from httpx import Response
from nonebot import on_command, on_request, on_notice, on_message
from nonebot.adapters.onebot.v11 import Event, GroupRequestEvent, GroupDecreaseNoticeEvent, \
    FriendRequestEvent, \
    Bot, GroupIncreaseNoticeEvent, Message, GroupMessageEvent, ActionFailed, GroupBanNoticeEvent
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
        if module_name not in self.config["modules"]:
            self.config["modules"][module_name] = {"state": True}
            self.save()

    def init_value(self, module_name: str, key: str, default_value: Any = None):
        if key not in self.config["modules"][module_name] and default_value is not None:
            self.config["modules"][module_name][key] = default_value
            self.save()
        return self.config["modules"][module_name][key]

    def set_value(self, module_name: str, key: str, value: Any):
        self.config["modules"][module_name][key] = value
        self.save()
        return self

    def get_module(self, module_name: str) -> Any | dict:
        if module_name in self.config["modules"]:
            return self.config["modules"][module_name]
        return None

    def get_admins(self) -> list[str]:
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

    def remove_user(self, uid: str):
        del self.config["black-list"][uid]
        self.save()

    def get_user(self, uid: str):
        return self.config["black-list"][uid]


async def get_user_name(bot: Bot, uid: str):
    """获取用户名"""
    return (await bot.get_stranger_info(user_id=int(uid), no_cache=True))["nickname"]


async def get_group_name(bot: Bot, gid):
    """获取群组名称"""
    return (await bot.get_group_info(group_id=int(gid), no_cache=True))["group_name"]


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


async def get(url: str, timeout: float = 5, *args, **kwargs) -> Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(url, *args, **kwargs)
        return r


async def post(url: str, params: dict) -> Response:
    async with httpx.AsyncClient() as client:
        r = await client.post(url, params=params)
        return r


@on_command("toggle", priority=1, block=False).handle()
async def on_handle(matcher: Matcher, event: Event):
    if not is_admin(event):
        return
    arg = parse_arg(event.get_plaintext())
    if len(arg) == 0:
        await matcher.finish("[Toggle] 参数错误 -> /toggle <moduleName: string>")
    module_name: str = arg[0]
    current_state: Any | bool = utils.get_state(module_name)
    if current_state is None:
        await matcher.finish(f"[Toggle] 模块 {module_name} 不存在")
    utils.set_state(module_name, not current_state)
    await matcher.finish(
        f"[Toggle] 模块{module_name}状态切换成功, 现在状态为{'启用' if not current_state else '禁用'}")


@on_command("bot").handle()
async def on_handle(matcher: Matcher, event: Event):
    await matcher.finish(BOT_DOC)


@on_command("bl", aliases={"blacklist", "blocked"}).handle()
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
            return
        sub1 = arg[0]
        match sub1:
            case "add":
                uid = arg[1]
                reason: str = "idk"
                if len(arg) >= 3:
                    reason = " ".join(arg[2:])
                in_type = black_list.in_black_list(uid)
                black_list.add_user(uid, reason)
                await matcher.finish(
                    f"[BlackList] 成功{('修改 ' + uid + ' 的封禁原因') if in_type else ('添加 ' + uid + ' 到黑名单中')}")
            case "remove":
                uid = arg[1]
                if not black_list.in_black_list(uid):
                    await matcher.finish(f"[BlackList] UID{uid} 不存在于黑名单中")
                black_list.remove_user(uid)
                await matcher.finish(f"[BlackList] 成功解除{uid}的封禁")
    else:
        await matcher.finish("[BlackList] 错误的使用方法 -> /bl add|remove|get [sub-args]")


# Module AutoAccept

@on_request().handle()
async def on_handle(bot: Bot, matcher: Matcher, event: FriendRequestEvent):
    if not utils.get_state("auto-accept"):
        return
    raw: dict = json.loads(event.json())
    flag = raw["flag"]
    uid = event.get_user_id()
    await bot.set_friend_add_request(flag=flag, approve=not black_list.in_black_list(uid))


@on_request().handle()
async def on_handle(bot: Bot, matcher: Matcher, event: GroupRequestEvent):
    if not utils.get_state("auto-accept"):
        return
    group: str = str(event.group_id)
    user: str = event.get_user_id()
    raw: dict = json.loads(event.json())
    comment: str = raw["comment"]
    flag = raw["flag"]
    sub_type: str = raw["sub_type"]
    is_invite = "invitor_id" in raw

    if sub_type == "invite":
        await bot.set_group_add_request(flag=flag, sub_type=sub_type, approve=(user in utils.get_admins()),
                                        reason="你不可以邀请")
        if user not in utils.get_admins():
            await bot.send_private_msg(user_id=int(user),
                                       message="你尝试邀请机器人, 但是你不是管理员")
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
        elif get_accept_type(group) == "invite-code":
            await bot.set_group_add_request(flag=flag, sub_type=sub_type,
                                            approve=use_activate_code(comment.split("：")[1], group),
                                            reason="邀请码错误")


def use_activate_code(code: str, group: str) -> bool:
    """Use the action code"""
    activate_codes: list = utils.init_value("auto-accept", "groups")[group]["activate-codes"]
    if code in activate_codes:
        activate_codes.remove(code)
        utils.set_value("auto-accept", "activate-codes", activate_codes)
        return True  # OK
    return False  # Code not found


def get_group(group_id: str) -> dict | None:
    groups: dict = utils.init_value("auto-accept", "groups")
    if group_id in groups:
        return groups[group_id]
    return None


def get_accept_type(group_id: str) -> None | str:
    return get_group(group_id)["type"] if get_group(group_id) is not None else None


utils.init_module("auto-accept")
utils.init_value("auto-accept", "groups", {})


# Module AutoAccept end

# Module AutoWelcome

@on_notice().handle()
async def on_handle_join(bot: Bot, matcher: Matcher, event: GroupIncreaseNoticeEvent):
    if not check("auto-welcome", event):
        return
    uid = event.get_user_id()
    gid = str(event.group_id)
    auto_kick: bool = utils.init_value("auto-welcome", "auto-kick")
    groups: dict = utils.init_value("auto-welcome", "groups")
    if event.get_user_id() == bot.self_id:
        await matcher.finish(
            f"[AutoWelcome] 我是{BOT_NAME}, 我可以替代Q群管家, 如果你要获得更好的群聊体验, 请把我设置成管理员并删除Q群管家")
    if gid not in groups:
        return
    if black_list.in_black_list(uid) and auto_kick:
        await bot.set_group_kick(group_id=int(gid), user_id=int(uid), reject_add_request=False)
    message: str = groups[gid].replace("%name%", f"[CQ:at,qq={uid}] ")
    await matcher.finish(Message(message))


@on_notice().handle()
async def on_handle_left(bot: Bot, matcher: Matcher, event: GroupDecreaseNoticeEvent):
    if not check("auto-welcome", event):
        return
    leave_message: str = utils.init_value("auto-welcome", "leave-message")
    uid = event.get_user_id()

    user_name = await get_user_name(bot, uid)
    message = leave_message.replace("%name%", f"{user_name} ({uid})")
    await matcher.finish(Message(message))


utils.init_module("auto-welcome")
utils.init_value("auto-welcome", "auto-kick", True)
utils.init_value("auto-welcome", "leave-message", "%name% left")
utils.init_value("auto-welcome", "groups", {})


# Module AutoWelcome end


# Module get Minecraft Username start
async def get_exact_minecraft_name(username: str) -> None | str:
    """获取有大小写的Minecraft用户名称"""
    if len(username) > 17:
        r = await get("https://sessionserver.mojang.com/session/minecraft/profile/" + username)
        return r.json()["name"]
    r = await get("https://api.mojang.com/users/profiles/minecraft/" + username)
    if r.status_code == 200:
        return r.json()["name"]
    return None


# Module get Minecraft Username end


# Module OF cape start
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
        return
    arg = parse_arg(event.get_plaintext())
    if len(arg) == 0:
        await matcher.finish("[OF Cape] 获取玩家OF披风 -> /ofcape <playerUuid|playerUserName> [proxy]")
    elif len(arg) == 1:
        username = arg[0]
        real_username: str = await get_exact_minecraft_name(username)
        of = await get_of_cape(real_username)
        if of["state"]:
            await matcher.finish(
                Message(
                    "[OF Cape] Cape of {}\nURL: {}\n[CQ:image,file={},cache=0]".format(of["username"], of["cape"] if of[
                        "cape"] else "Default cape", of["image"])))
        else:
            await matcher.finish("[OF Cape] 玩家{}没有披风".format(of["username"]))
    elif len(arg) == 2:
        username = arg[0]
        proxy = arg[1]
        real_username: str = await get_exact_minecraft_name(username)
        of = await get_of_cape(real_username, proxy)
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

# Module Mojang cape start
async def get_mojang_cape(username: str) -> dict:
    username = await get_exact_minecraft_name(username)
    mojang_cape_url = await get("https://api.capes.dev/load/" + username)
    checker = mojang_cape_url.json()['minecraft']['msg']
    if checker == "Player has no cape":
        return {"state": False, "username": username}
    else:
        mojang_cape_still = mojang_cape_url.json()['minecraft']['stillImageUrl'] + ".png"
        mojang_cape_front = mojang_cape_url.json()['minecraft']['frontImageUrl'] + ".png"
        return {"state": True, "image_still": mojang_cape_still, "image_front": mojang_cape_front, "username": username}


@on_command("mojangcape").handle()
async def on_handle(matcher: Matcher, event: Event):
    if not utils.get_state("mojangcape"):
        return
    arg = parse_arg(event.get_plaintext())
    if len(arg) == 1:
        username = arg[0]
        mojang = await get_mojang_cape(username)
        if mojang["state"]:
            await matcher.finish(
                Message(
                    "[Mojang Cape] Cape of {}\n展开图：[CQ:image,file={},cache=0]正面图：[CQ:image,file={},cache=0]".format(
                        mojang["username"], mojang["image_still"], mojang["image_front"])))
        else:
            await matcher.finish("[Mojang Cape] 玩家{}没有披风".format(mojang["username"]))
    else:
        await matcher.finish("[Mojang Cape] 格式错误\n输入格式 -> /mojangcape <playerUuid|playerUserName>")


utils.init_module("mojangcape")


# Module Mojang cape end


# Module AutoMute start
@on_message().handle()
async def on_handle(bot: Bot, event: GroupMessageEvent):
    uid = event.get_user_id()
    gid = event.group_id
    msg = event.get_plaintext()
    msg_id = event.message_id
    if uid in utils.get_admins() + utils.init_value("auto-mute", "white-list") or not utils.get_state("auto-mute"):
        return
    if gid in utils.init_value("recall", "enable-groups", []) and uid not in utils.get_admins():
        await bot.delete_msg(message_id=msg_id)
    if black_list.in_black_list(uid):
        try:
            await bot.delete_msg(message_id=msg_id)
            await bot.set_group_ban(group_id=gid, user_id=int(uid), duration=utils.init_value("auto-mute", "mute-time"
                                                                                                           "-blocked") * 60)
            await bot.send_private_msg(user_id=int(uid),
                                       message=f"[AutoMute] 你的uid存在于机器人黑名单中, 如果你认为你的封禁是错误的, 请联系任意管理员进行申诉\nReason:"
                                               f" {black_list.get_user(uid)['reason']}\n(请勿回复此消息)")
        except ActionFailed:
            pass
        return
    blocked_words = utils.init_value("auto-mute", "blocked-words", [])
    blocked_pattern = utils.init_value("auto-mute", "blocked-pattern", [])
    full_match = utils.init_value("auto-mute", "blocked-words-full-match", [])
    mute_time = utils.init_value("auto-mute", "mute-time") * 60
    bypass_long = utils.init_value("auto-mute", "bypass-long")
    should_mute = False
    if len(msg.split("\n")) > utils.init_value("auto-mute", "long-message-lines"):
        try:
            await bot.delete_msg(message_id=msg_id)
            await bot.set_group_ban(group_id=gid, user_id=int(uid), duration=utils.init_value("auto-mute", "mute-time"
                                                                                                           "-long-message") * 60)
            await bot.send_private_msg(user_id=int(uid),
                                       message=f"[AutoMute] 群{gid}禁止发送长消息")
        except ActionFailed:
            pass
        return
    for word in blocked_words:
        if word in msg and len(msg) > bypass_long:
            should_mute = True
    for pattern in blocked_pattern:
        if re.match(pattern, msg):
            should_mute = True
    for s in full_match:
        if msg == s:
            should_mute = True
    if should_mute:
        try:
            await bot.delete_msg(message_id=msg_id)
            await bot.set_group_ban(group_id=gid, user_id=int(uid), duration=mute_time)
            await bot.send_private_msg(user_id=int(uid), message="[AutoMute] 你发送的消息存在违禁词, 如果你认为此消息是错误的, 请给任意管理员反馈, "
                                                                 "以帮助我们改善机器人(请勿回复此消息)")
        except ActionFailed:
            pass


utils.init_module("auto-mute")
utils.init_value("auto-mute", "white-list", [])  # 白名单
utils.init_value("auto-mute", "blocked-words", [])  # 屏蔽词
utils.init_value("auto-mute", "blocked-pattern", [])  # 使用re匹配的屏蔽词
utils.init_value("auto-mute", "blocked-words-full-match", [])  # 完全匹配的屏蔽词
utils.init_value("auto-mute", "long-message-lines", 10)  # 长消息过滤(-1为关闭)
utils.init_value("auto-mute", "bypass-long", 50)  # 防止误检测
utils.init_value("auto-mute", "mute-time", 10)  # 禁言时间(触发关键词)
utils.init_value("auto-mute", "mute-time-blocked", 1440)  # 禁言时间(黑名单)
utils.init_value("auto-mute", "mute-time-long-message", 1)  # 禁言时间(发送长消息)
utils.init_value("auto-mute", "mute-blocked-users", True)  # 禁言黑名单用户


# Module AutoMute end


# Module Player Info start
async def get_player_info(player: str):
    uuid = player
    if not len(player) > 17:
        r = await get("https://api.mojang.com/users/profiles/minecraft/" + player)
        j = r.json()
        uuid = None if "errorMessage" in j else j["id"]
    r = await get("https://sessionserver.mojang.com/session/minecraft/profile/" + uuid)
    j = r.json()
    if "errorMessage" in j:
        return None
    username = j["name"]
    data = json.loads(base64.b64decode(j["properties"][0]["value"]).decode("utf-8"))
    skin = data["textures"]["SKIN"]["url"]
    model = "slim" if "metadata" in data["textures"]["SKIN"] else "normal"
    return {
        "uuid": uuid,
        "username": username,
        "skin": skin,
        "skin-model": model
    }


# Module Player Info end


# Module Minecraft start
@on_command("mc", aliases={"minecraft"}).handle()
async def on_handle(matcher: Matcher, bot: Bot, event: Event):
    if not utils.get_state("minecraft"):
        return
    args = parse_arg(event.get_plaintext())
    if len(args) == 1:
        player = args[0]
        try:
            info = await get_player_info(player)
            msg = Message(
                f"[MC] UserName: {info['username']}\n"
                f"UUID: {info['uuid']}\n"
                f"NameMC: https://namemc.com/profile/{info['uuid']}\n"
                f"Cape: 使用 /ofcape {info['username']} 或 /mojangcape {info['username']} 进行查询\n"
                f"SkinUrl: {info['skin']} (Model: {info['skin-model']})\n"
                f"[CQ:image,file={info['skin']},cache=0]"
            )
        except:
            msg = f"[MC] Player {player} not found."
    else:
        msg = "[MC] /mc <playerUuid|playerUserName>"
    await matcher.finish(msg)


utils.init_module("minecraft")


# Module Minecraft end


# Module Hypixel start
async def get_hypixel_info(username: str, key) -> dict:
    info = await get_player_info(username)
    uuid = info['uuid']

    u1 = "https://api.hypixel.net/player?key={}&uuid={}".format(key, uuid)
    u2 = "https://api.hypixel.net/recentgames?key={}&uuid={}".format(key, uuid)
    status_api = "https://api.hypixel.net/status?key={}&uuid={}".format(key, uuid)
    guild_api = "https://api.hypixel.net/guild?key={}&player={}".format(key, uuid)

    player = await get(u1)
    recentgames = await get(u2)
    status = await get(status_api)
    guild = await get(guild_api)

    if player.status_code != 200:
        return {"state": False, "username": username}
    if recentgames.status_code != 200:
        return {"state": False, "username": username}
    if status.status_code != 200:
        return {"state": False, "username": username}
    if guild.status_code != 200:
        return {"state": False, "username": username}

    p = player.json()['player']
    r = recentgames.json()['games']
    s = status.json()['session']['online']
    g = guild.json()['guild']['name']

    displayname = p['displayname']
    rank = p['newPackageRank']
    langrage = p['userLanguage']
    firstlogin: int = p['firstLogin']
    lastlogin: int = p['lastLogin']

    firstlogin_local = time.localtime(firstlogin / 1000)
    firstlogin_dt = time.strftime("%Y-%m-%d %H:%M:%S", firstlogin_local)
    lastlogin_local = time.localtime(lastlogin / 1000)
    lastlogin_dt = time.strftime("%Y-%m-%d %H:%M:%S", lastlogin_local)

    if s == "true":
        st = "在线"
    else:
        st = "离线"

    if not r: r = "无"

    return {"state": True,
            "dn": displayname,
            "rank": rank,
            "fl": firstlogin_dt,
            "ll": lastlogin_dt,
            "rg": r,
            "lan": langrage,
            "status": st,
            "guild": g
            }


@on_command("hyp", aliases={"hypixel"}).handle()
async def on_handle(matcher: Matcher, event: Event):
    if not utils.get_state("hypixel"):
        return
    args = parse_arg(event.get_plaintext())
    key = utils.init_value("hypixel", "hypkey")
    if len(args) == 1:
        player = args[0]
        info = await get_hypixel_info(player, key)
        if info["state"]:
            msg = Message(
                f"[HYPIXEL] {info['dn']}的Hypixel用户数据：\n"
                f"会员等级：{info['rank']}\n"
                f"工会：{info['guild']}\n"
                f"最近一次游戏：{info['rg']}\n"
                f"当前状态：{info['status']}\n"
                f"玩家语言：{info['lan']}\n"
                f"首次登录：{info['fl']}\n"
                f"最后登录：{info['ll']}\n"
            )
        else:
            msg = f"[HYPIXEL] Player {player} not found."
    else:
        msg = "[HYPIXEL] /hyp <playerUuid|playerUserName>"

    await matcher.finish(msg)


utils.init_module("hypixel")
utils.init_value("hypixel", "hypkey", "")

# Module Hypixel end


# Module renameAll start
rename_state = False


@on_command("renameall").handle()
async def on_handle(matcher: Matcher, bot: Bot, event: GroupMessageEvent):
    global rename_state
    if event.get_user_id() not in utils.get_admins():
        return
    args = parse_arg(event.get_plaintext())
    if len(args) == 0:
        await matcher.finish("[Rename] 给成员编序号 -> /renameall [--reset] [--cancel]")
    if "--cancel" in args:
        rename_state = False
        await matcher.finish("[Rename] 操作成功执行")
    target_name = " ".join(args[0:])
    if "--reset" in args:
        target_name = ""
    if rename_state:
        await matcher.finish("[Rename] 不支持同时重命名多个群, 如果这个是bug, 请使用 /renameall --cancel 重置状态!")
    gid = event.group_id
    member_list = await bot.get_group_member_list(group_id=gid)
    await matcher.send("[Rename] 开始重命名, 预计时间: {}s".format(2 * len(member_list)))
    rename_state = True
    time_start = time.time()
    for i, user in enumerate(member_list):
        if not rename_state:
            await matcher.finish("[Rename] canceled")
        target_uid = int(user["user_id"])
        if int(bot.self_id) == target_uid:
            continue
        await bot.set_group_card(group_id=gid, user_id=target_uid,
                                 card=(target_name + f"#{'0' * (4 - len(str(i)))}{i}") if target_name else "")
        await asyncio.sleep(2)
    rename_state = False
    await matcher.finish("[Rename] Done in {}s".format(round(time.time() - time_start, 2)))


@on_command("rename").handle()
async def on_handle(matcher: Matcher, bot: Bot, event: GroupMessageEvent):
    uid = event.get_user_id()
    gid = event.group_id
    if uid not in utils.get_admins():
        return
    card = " ".join(parse_arg(event.get_plaintext()))
    await bot.set_group_card(user_id=int(bot.self_id), group_id=gid, card=card)
    await matcher.finish(f"[Rename] 已将Bot自身的群昵称设置为 {card}")


@on_command("title").handle()
async def on_handle(matcher: Matcher, bot: Bot, event: GroupMessageEvent):
    uid = event.get_user_id()
    gid = event.group_id
    if uid not in utils.get_admins():
        return
    args = parse_arg(event.get_plaintext())
    if len(args) > 1:
        await matcher.finish("[Title] 设置专属头衔 -> /title <target> [title]>\n"
                             "需要注意的是, 如果要设置超长头衔, title中不能包含中文")
    else:
        target = args[0]
        title = "-".join(args[1:]) if len(args) >= 2 else ""
        await bot.set_group_special_title(group_id=gid, user_id=int(target), special_title=title, duration=-1)
        await matcher.finish("[Title] 设置成功")


@on_command("renametarget").handle()
async def on_handle(matcher: Matcher, bot: Bot, event: GroupMessageEvent):
    uid = event.get_user_id()
    gid = event.group_id
    if uid not in utils.get_admins():
        return
    args = parse_arg(event.get_plaintext())
    if len(args) <= 1:
        await matcher.finish("[Rename] 命名某个UID -> /renametarget <target-uid> <nickname>")
    target = args[0]
    card = " ".join(args[1:])
    await bot.set_group_card(user_id=int(target), group_id=gid, card=card)
    await matcher.finish(f"[Rename] 已将 {await get_user_name(bot, target)} ({target}) 的昵称设置为 {card}")


@on_command("renamegroup", aliases={"renameg"}).handle()
async def on_handle(matcher: Matcher, bot: Bot, event: GroupMessageEvent):
    uid = event.get_user_id()
    gid = event.group_id
    if uid not in utils.get_admins():
        return
    name = " ".join(parse_arg(event.get_plaintext()))
    await bot.set_group_name(group_id=gid, group_name=name)
    await matcher.finish(f"[Rename] 成功将群组名称设置为 {name}")


@on_command("setprofile").handle()
async def on_handle(matcher: Matcher, bot: Bot, event: Event):
    """设置Bot自身的资料卡"""
    uid = event.get_user_id()
    if uid not in utils.get_admins():
        return
    name = " ".join(parse_arg(event.get_plaintext()))
    if not name.replace(" ", ""):
        await matcher.finish("[Rename] 设置Bot资料卡 -> /setprofile <nickName>")
    await bot.set_qq_profile(nickname=name)
    await matcher.finish(f"[Rename] 成功将Bot资料卡设置为 {name}")


@on_command("phone").handle()
async def on_handle(matcher: Matcher, bot: Bot, event: Event):
    """设置机型"""
    uid = event.get_user_id()
    if uid not in utils.get_admins():
        return
    name = " ".join(parse_arg(event.get_plaintext()))
    if not name.replace(" ", ""):
        await matcher.finish("[Rename] 设置Bot在线机型(此功能已被和谐) -> /phone <nickName>")
    await bot._set_model_show(model=name, model_show="1")
    await matcher.finish(f"[Rename] 成功将Bot在线机型设置为 {name}")


# Module renameAll end

# Module memberManager start
@on_command("kick").handle()
async def on_handle(matcher: Matcher, bot: Bot, event: GroupMessageEvent):
    uid = event.get_user_id()
    gid = event.group_id
    if uid not in utils.get_admins():
        return
    args = parse_arg(event.get_plaintext())

    async def kick(target):
        try:
            if target in utils.get_admins():
                raise ActionFailed()
            await bot.set_group_kick(user_id=int(target), group_id=gid, reject_add_request=False)
        except ActionFailed:
            await matcher.finish(f"[MemberManager] 你没有权限踢出{target}")

    if len(args) == 1:
        target_uid = args[0]
        await kick(target_uid)
    elif len(args) >= 2:
        target_uid = args[0]
        reason = " ".join(args[1:])
        await kick(target_uid)
        black_list.add_user(target_uid, reason)
    else:
        await matcher.finish("[MemberManager] 踢出群成员 -> /kick <uid> [bl-reason]")


@on_command("mute").handle()
async def on_handle(matcher: Matcher, bot: Bot, event: GroupMessageEvent):
    uid = event.get_user_id()
    gid = event.group_id
    if uid not in utils.get_admins():
        return
    args = parse_arg(event.get_plaintext())

    async def mute(target, duration=0):
        try:
            if target in utils.get_admins():
                raise ActionFailed()
            await bot.set_group_ban(user_id=int(target), group_id=gid, duration=duration)
            await matcher.finish(f"[MemberManager] 禁言{target}成功")
        except ActionFailed:
            await matcher.finish(f"[MemberManager] 你没有权限禁言{target}")

    if len(args) == 1:
        target_uid = args[0]
        await mute(target_uid)
    elif len(args) >= 2:
        target_uid = args[0]
        duration = 0
        t = args[1].split(":")
        if len(t) == 3:
            duration += int(t[0]) * 3600 * 24  # d
            duration += int(t[1]) * 3660  # h
            duration += int(t[2]) * 60  # m
        elif len(t) == 2:
            duration += int(t[0]) * 3600  # h
            duration += int(t[1]) * 60  # m
        elif len(t) == 1:
            duration += int(t[0]) * 60  # m
        await mute(target_uid, duration)
    else:
        await matcher.finish("[MemberManager] 禁言群成员 -> /mute <uid> [time]\ntime参数不填或为0时代表解除禁言")


@on_notice().handle()
async def on_handle(bot: Bot, event: GroupBanNoticeEvent):
    uid = event.get_user_id()
    gid = event.group_id
    if uid in utils.get_admins():
        try:
            await bot.set_group_ban(group_id=gid, user_id=int(uid), duration=0)
        except ActionFailed:
            pass


@on_command("muteall").handle()
async def on_handle(matcher: Matcher, bot: Bot, event: GroupMessageEvent):
    gid = str(event.group_id)
    new_groups: list = utils.init_value("recall", "enable-groups")
    if gid in utils.init_value("recall", "enable-groups"):
        state = False
        new_groups.remove(gid)
    else:
        state = True
        new_groups.append(gid)
    utils.set_value("recall", "enable-groups", new_groups)
    await matcher.send(
        f"[MuteAll] 群组{await get_group_name(bot, gid)} ({gid})已" + (
            "添加到自动撤回列表中" if state else "从自动撤回列表中删除"))


@on_message().handle()
async def on_handle(matcher: Matcher, bot: Bot, event: GroupMessageEvent):
    """Mute All handle"""
    gid = str(event.group_id)
    groups: list = utils.init_value("recall", "enable-groups")
    if gid in groups and event.get_user_id() not in utils.get_admins():
        await bot.delete_msg(message_id=event.message_id)  # recall message


utils.init_module("recall")
utils.init_value("recall", "enable-groups", [])


@on_command("w", aliases={"pm", "whisper", "echopm"}).handle()
async def on_handle(bot: Bot, event: Event, matcher: Matcher):
    if event.get_user_id() not in utils.get_admins():
        return
    arg = parse_arg(event.get_plaintext())
    if len(arg) < 2:
        await matcher.finish(
            "[MemberManager] 私信某人-> /w <target-uid: int> <message: str>\n别名: /pm /whisper /echopm")
    target = arg[0]
    msg = " ".join(arg[1:])
    try:
        await bot.send_private_msg(user_id=int(target), message=Message(msg))
        await matcher.finish(f"[MemberManager] 私信 {await get_user_name(bot, target)} ({target}) 成功")
    except ActionFailed:
        await matcher.finish(f"[MemberManager] 私信{target}失败, 可能没加好友或被对方屏蔽")
    except ValueError:
        await matcher.finish(f"[MemberManager] UID不正确")


@on_command("echo", aliases={"say"}).handle()
async def on_handle(matcher: Matcher, event: Event):
    """Echo handle"""
    if event.get_user_id() not in utils.get_admins():
        return
    arg = parse_arg(event.get_plaintext())
    if len(arg) == 0:
        await matcher.finish("[Echo] 复读 -> /echo <message>")
    await matcher.finish(" ".join(arg))


# Module memberManager end

# Module Bilibili
# idea from https://github.com/catandA/BilibiliBOT-1
bv_api = "https://api.bilibili.com/x/web-interface/view?bvid="
av_api = "https://api.bilibili.com/x/web-interface/view?avid="

pattern_url = re.compile(
    r"(http:)?(https:)?(//)?((([a-zA-Z0-9_-])+(\.)?){1,2}\.)?(bilibili.com)+(:\d+)?(\/((\.)?(\?)?=?&?%?["
    r"#!a-zA-Z0-9_-](\?)?)*)*$")


async def get_video_info_msg(bv: str):
    url = bv_api + bv
    res = await get(url)
    out = res.json()
    if out["code"] != 0:
        return None
    data: dict = out["data"]
    pic_url: str = data["pic"]
    title: str = data["title"]
    desc: str = data["desc"]
    real_bv: str = data['bvid']
    link: str = "https://bilibili.com/video/" + real_bv
    msg = Message(f"""[Bilibili] Video info of {real_bv}
{link}
标题: {title}
介绍: {desc}
[CQ:image,file={pic_url}]""")
    return msg


@on_command("bilibili", aliases={"bv"}).handle()
async def on_handle(matcher: Matcher, event: Event):
    if not utils.get_state("bilibili"):
        return
    arg = parse_arg(event.get_plaintext())
    if len(arg) != 1:
        await matcher.finish(
            "[Bilibili] 获取视频信息 -> /bilibili <bv: str> 别名 /bv\n灵感来源于github (catandA/BilibiliBot-1)")
    bv = arg[0]
    info = await get_video_info_msg(bv)
    if info is None:
        await matcher.finish(f"[Bilibili] {bv} 视频不存在, 此指令只能根据BV号查询, 暂时不支持AV")
    await matcher.finish(info)


@on_message().handle()
async def on_handle(matcher: Matcher, event: Event):
    """Find url"""
    msg = event.get_plaintext()
    if utils.get_state("bilibili"):
        # Match for bilibili
        all_matches = re.findall(pattern_url, msg)
        match: tuple[str]
        for match in all_matches:
            ur: str = match[9][1:].split("?")[0]
            bv: str = ur.replace("/", "")
            try:
                await matcher.send(await get_video_info_msg(bv))
            except TypeError:
                await matcher.send(f"[Bilibili] {bv} 不是正确的BV号")


utils.init_module("bilibili")


# Module Bilibili end

# Module Spammer start
@on_command("spammer").handle()
async def on_handle(matcher: Matcher, event: GroupMessageEvent):
    msg = event.get_plaintext()
    if event.get_user_id() not in utils.get_admins():
        return
    arg = parse_arg(msg)
    if len(arg) < 2:
        await matcher.finish("[Spammer] 刷屏器 -> /spammer <count: int> <message: str>")
    try:
        count = int(arg[0])
    except ValueError:
        await matcher.finish("[Spammer] count must be a integer")
    message = Message(" ".join(arg[1:]))
    for i in range(count):
        await matcher.send(message)
        await asyncio.sleep(0.05)  # Anti MA HUA TENG


# Module Spammer end

# Module ServiceState start
@on_command("services").handle()
async def on_handle(matcher: Matcher, event: Event):
    """Handle services state"""
    api_dict: dict = utils.init_value("service-state", "api-list")
    timeout = utils.init_value("service-state", "timeout")
    arg = parse_arg(event.get_plaintext())
    msg: str = "[ServiceState] "
    if len(api_dict) == 0 and len(arg) == 0:
        msg += "\n队列中无服务, 使用/services add <api>添加服务"
    elif arg[0] == "help":
        msg += ("服务状态查询\n"
                "添加服务: /services add <name> <api: str> [body: json]\n"
                "删除服务: /services remove <name>\n"
                "设置/查询时间上限: /services timeout [timeout: float]\n")
    elif arg[1] == "add" and event.get_user_id() in utils.get_admins():
        if len(arg) < 3:
            msg += "添加服务 -> /services add <name> <api: str> [body: json]"
        else:
            name = arg[2]
            service = arg[3]
            data = {}
            if len(arg) > 3:
                data = " ".join(arg[3:])
            api_dict[name] = {"service": service, "data": data}
            utils.set_value("service-state", "api-list", api_dict)
            msg += "成功添加服务"
    elif len(arg) == 0:
        msg += "服务状态\n如果需要该命令的帮助请输入 /services help"
        for name, value in api_dict.items():
            try:
                r = await get(value["service"], params=value["data"], timeout=timeout)
                status = r.status_code
                msg += f"\n[{status}] {name}"
            except Exception:
                msg += f"\n[访问超时] {name}"
    else:
        msg += "没有权限使用这个指令或该指令不存在"
    await matcher.finish(msg)


utils.init_module("service-state")
utils.init_value("service-state", "api-list", {})
utils.init_value("service-state", "timeout", 5)
# Module ServerState end
