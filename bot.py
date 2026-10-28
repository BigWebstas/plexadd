"""Telegram bot: /movie <title> adds to Radarr, /tv <title> adds to Sonarr, /id shows your user ID, /status checks both apps. Stdlib only."""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def request(method, url, headers=None, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data, {"Content-Type": "application/json", **(headers or {})}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        # Sonarr/Radarr validation errors are [{"errorMessage": ...}]; surface them to the user.
        try:
            detail = "; ".join(x["errorMessage"] for x in json.load(e))
        except (ValueError, KeyError, TypeError):
            detail = e.reason
        raise RuntimeError(detail) from e


class Arr:
    """A Sonarr or Radarr instance (both speak the same v3 API for what we need)."""

    def __init__(self, name, base_url, api_key, path, id_field, lookup_prefix, add_defaults):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-Api-Key": api_key}
        self.path = path
        self.id_field = id_field
        self.lookup_prefix = lookup_prefix
        self.add_defaults = add_defaults

    def call(self, method, endpoint, body=None):
        return request(method, f"{self.base_url}/api/v3/{endpoint}", self.headers, body)

    def search(self, term):
        return self.call("GET", f"{self.path}/lookup?term={urllib.parse.quote(term)}")

    def status(self):
        """One line: version and any problems that would break health or adding."""
        try:
            version = self.call("GET", "system/status")["version"]
            problems = [h["message"] for h in self.call("GET", "health") if h["type"] in ("warning", "error")]
            if not self.call("GET", "rootfolder"):
                problems.append("No root folder configured")
            if not self.call("GET", "qualityprofile"):
                problems.append("No quality profile configured")
        except (OSError, RuntimeError) as e:
            return f"❌ {self.name}: {getattr(e, 'reason', e)}"
        if problems:
            return f"⚠️ {self.name} {version}\n" + "\n".join(f"  • {p}" for p in problems)
        return f"✅ {self.name} {version}"

    def add(self, ident):
        item = self.search(f"{self.lookup_prefix}:{ident}")[0]
        self.call("POST", self.path, {
            **item,
            "qualityProfileId": self.call("GET", "qualityprofile")[0]["id"],
            "rootFolderPath": self.call("GET", "rootfolder")[0]["path"],
            "monitored": True,
            **self.add_defaults,
        })
        return label(item)


def label(item):
    return f"{item['title']} ({item['year']})" if item.get("year") else item["title"]


def parse_command(msg):
    """'/movie@bot dune' -> ('movie', 'dune'); non-commands give ('', text)."""
    command, _, query = msg.get("text", "").partition(" ")
    if not command.startswith("/"):
        return "", msg.get("text", "")
    return command[1:].split("@")[0], query


class Bot:
    def __init__(self, token, allowed_users, services):
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.allowed_users = allowed_users
        self.services = services  # {"movie": Arr, "tv": Arr}

    def api(self, method, **params):
        return request("POST", f"{self.base_url}/{method}", body=params, timeout=60)["result"]

    def handle_message(self, msg):
        kind, query = parse_command(msg)
        if kind == "status":
            return self.reply(msg, "\n".join(arr.status() for arr in self.services.values()))
        if kind not in self.services:
            return self.reply(msg, "Use /movie <title>, /tv <title> or /status")
        if not query.strip():
            return self.reply(msg, f"Usage: /{kind} <title>")
        arr = self.services[kind]
        results = arr.search(query.strip())[:5]
        if not results:
            return self.reply(msg, "No results")
        buttons = [[{
            "text": label(r) + (" ✅" if r.get("id") else ""),  # id is set when already in library
            "callback_data": f"{kind}:{r[arr.id_field]}",
        }] for r in results]
        self.reply(msg, "Pick one:", reply_markup={"inline_keyboard": buttons})

    def handle_callback(self, cb):
        self.api("answerCallbackQuery", callback_query_id=cb["id"])
        kind, _, ident = cb["data"].partition(":")
        try:
            text = f"Added: {self.services[kind].add(ident)}"
        except RuntimeError as e:
            text = f"Failed: {e}"
        msg = cb["message"]
        self.api("editMessageText", chat_id=msg["chat"]["id"], message_id=msg["message_id"], text=text)

    def reply(self, msg, text, **extra):
        self.api("sendMessage", chat_id=msg["chat"]["id"], text=text, **extra)

    def handle_update(self, update):
        event = update.get("message") or update.get("callback_query")
        if not event:
            return
        # Open to everyone so a new user can find the ID to put in ALLOWED_USER_IDS.
        if "message" in update and parse_command(event)[0] == "id":
            return self.reply(event, f"Your user ID: {event['from']['id']}")
        if event["from"]["id"] not in self.allowed_users:
            return
        try:
            if "message" in update:
                self.handle_message(event)
            else:
                self.handle_callback(event)
        except Exception as e:  # keep polling on any per-update failure
            print(f"error handling update {update['update_id']}: {e}", file=sys.stderr)
            if "message" in update:
                self.reply(event, f"Error: {e}")

    def run(self):
        offset = 0
        while True:
            try:
                updates = self.api("getUpdates", offset=offset, timeout=30,
                                   allowed_updates=["message", "callback_query"])
            except (OSError, RuntimeError) as e:
                print(f"polling failed: {e}", file=sys.stderr)
                time.sleep(5)
                continue
            for update in updates:
                offset = update["update_id"] + 1
                self.handle_update(update)


def main():
    env = os.environ
    try:
        services = {
            "movie": Arr("Radarr", env["RADARR_URL"], env["RADARR_API_KEY"], "movie", "tmdbId", "tmdb",
                         {"addOptions": {"searchForMovie": True}}),
            "tv": Arr("Sonarr", env["SONARR_URL"], env["SONARR_API_KEY"], "series", "tvdbId", "tvdb",
                      {"seasonFolder": True, "addOptions": {"searchForMissingEpisodes": True}}),
        }
        token = env["TELEGRAM_TOKEN"]
        allowed = {int(x) for x in env["ALLOWED_USER_IDS"].split(",") if x.strip()}
    except KeyError as e:
        sys.exit(f"missing env var {e}")
    if not allowed:
        sys.exit("ALLOWED_USER_IDS has no user IDs")
    Bot(token, allowed, services).run()


if __name__ == "__main__":
    main()
