import os
import time
import asyncio
from aiohttp import web
from twitchio.ext import commands
from collections import defaultdict

HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <title>Twitch Chat Frequency</title>
    <style>
        body {
            margin: 0;
            overflow: hidden;
            background-color: #111;
        }
        .container {
            display: flex;
            overflow-x: auto;
            align-items:flex-start;
            width:fit-content;
        }
        .user-column {
           
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-start;
            font-family: monospace;
            color: white;
            transition: background-color 0.3s;
            max-width:20px;

        }
        .time {
            font-size: 12px;
            margin-top: 4px;
        }
        .username {
            font-size: 5px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 100%;
            writing-mode:tb;
            text-orientation:mixed;
            left:inherit;
            color:black;
            max-width:10px;
        }
        .times {
            writing-mode:lr;
            list-style-type:none;
            max-width:10px;
            padding-top:35px;
            position:sticky;
        }
        .name{
            position:absolute;
        }
    </style>
</head>
<body>
    <div class="container"></div>
    <script>
        const container = document.querySelector('.container');
        
function interpolate(from, to, progress) {
  return from + (to - from) * progress;
}

function getColor(timeDiff) {
  // If timeDiff is missing or over the max, return white.
  if (timeDiff === null) return '#ffffff';
  if (timeDiff >= 90) return '#ffffff';

  let h, s, l, progress;

  // Segment 1: 0 to 15 seconds: deep dark red -> orange-yellow
  if (timeDiff <= 15) {
    progress = timeDiff / 15;
    // deep dark red: h=0, s=100, l=20
    // orange-yellow: h=40, s=100, l=50
    h = interpolate(0, 40, progress);
    s = interpolate(100, 100, progress);
    l = interpolate(20, 50, progress);
  }
  // Segment 2: 15 to 45 seconds: orange-yellow -> green
  else if (timeDiff <= 45) {
    progress = (timeDiff - 15) / 30;
    // orange-yellow: h=40, s=100, l=50  
    // green: h=120, s=100, l=50
    h = interpolate(40, 120, progress);
    s = interpolate(100, 100, progress);
    l = interpolate(50, 50, progress);
  }
  // Segment 3: 45 to 75 seconds: green -> light green
  else if (timeDiff <= 75) {
    progress = (timeDiff - 45) / 30;
    // green: h=120, s=100, l=50
    // light green: h=120, s=50, l=80
    h = 120; // constant
    s = interpolate(100, 50, progress);
    l = interpolate(50, 80, progress);
  }
  // Segment 4: 75 to 90 seconds: light green -> white
  else { // (timeDiff between 75 and 90 seconds)
    progress = (timeDiff - 75) / 15;
    // light green: h=120, s=50, l=80
    // white: hsl(0, 0%, 100%)
    h = interpolate(120, 0, progress); // hue is less important for white
    s = interpolate(50, 0, progress);
    l = interpolate(80, 100, progress);
  }

  return `hsl(${h.toFixed(0)}, ${s.toFixed(0)}%, ${l.toFixed(0)}%)`;
}

        const ws = new WebSocket('ws://' + window.location.host + '/ws');
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            const user = data.user.replace(/[^a-zA-Z0-9_]/g, '');
            const timeDiff = data.time_diff;
            
            let column = document.getElementById(user);
            console.log(data.user, data.time_diff, data)
            if (!column) {
                column = document.createElement('div');
                column.className = 'user-column';
                column.id = user;
                column.innerHTML = `<div class="username"><div class="name">${data.user}</div><ul class="times"><li>${timeDiff !== null ? timeDiff.toFixed(1) + 's' : ''}<li></ul></div>`;
                container.appendChild(column);
                column.style.backgroundColor = "white";
            } else {
                let l = document.createElement('li');
                l.textContent = `${timeDiff.toFixed(1) + 's'}`
                l.style.backgroundColor = getColor(timeDiff);
                column.querySelector('.times').appendChild(l)
                    //timeDiff !== null ? timeDiff.toFixed(1) + 's' : 'New';
            }
            
            
            container.scrollTo({ left: container.scrollWidth, behavior: 'smooth' });
        };
    </script>
</body>
</html>
"""

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            token=os.getenv('TWITCH_TOKEN'),
            prefix='!',
            initial_channels=[os.getenv('TWITCH_CHANNEL')]
        )
        self.last_timestamps = defaultdict(float)
        self.websocket_clients = set()

    async def event_message(self, message):
        user = message.author.name
        now = time.time()
        last_time = self.last_timestamps[user]
        time_diff = now - last_time if last_time else None
        
        self.last_timestamps[user] = now

        data = {
            'user': user,
            'time_diff': round(time_diff, 1) if time_diff else None
        }

        for ws in self.websocket_clients:
            try:
                await ws.send_json(data)
            except:
                self.websocket_clients.remove(ws)

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    request.app['bot'].websocket_clients.add(ws)
    try:
        async for msg in ws:
            pass
    finally:
        request.app['bot'].websocket_clients.remove(ws)
    return ws

async def index(request):
    return web.Response(text=HTML_CONTENT, content_type='text/html')

async def main():
    PORT = 8080
    bot = Bot()
    app = web.Application()
    app['bot'] = bot
    app.router.add_get('/', index)
    app.router.add_get('/ws', websocket_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    print('starting visualizer, visible at http://localhost:8080')
    await site.start()
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())
