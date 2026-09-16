from __future__ import annotations
import threading, time, webbrowser


def run_tray(runtime, dashboard_url: str = 'http://127.0.0.1:8787/dashboard'):
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError as e:
        raise RuntimeError('Tray support is optional. Install with: pip install -e ".[desktop]"') from e

    from .daemon import NervousSystem
    stop_event = threading.Event()
    nervous = NervousSystem(runtime.config, runtime.memory, runtime.processes, runtime.watches, runtime.notifier,
                            routines=runtime.routines, orchestrator=runtime.orchestrator, model_manager=runtime.model_manager,
                            briefings=runtime.briefings, sessions=runtime.sessions, guardian=runtime.guardian, security_sensors=runtime.security_sensors)

    def loop():
        poll = max(5, int(runtime.config.get('daemon',{}).get('poll_seconds',15)))
        while not stop_event.wait(poll):
            try: nervous.tick()
            except Exception as exc: runtime.memory.add_event('tray_daemon_error', {'error': str(exc)})

    threading.Thread(target=loop, daemon=True).start()

    image = Image.new('RGB', (64,64), 'white')
    d = ImageDraw.Draw(image)
    d.ellipse((8,8,56,56), outline='black', width=4)
    d.ellipse((26,26,38,38), fill='black')

    def open_dashboard(icon, item): webbrowser.open(dashboard_url)
    def tick_now(icon, item): nervous.tick()
    def quit_app(icon, item):
        stop_event.set(); runtime.model_manager.sleep(); icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem('Open Control Center', open_dashboard),
        pystray.MenuItem('Run health tick', tick_now),
        pystray.MenuItem('Quit', quit_app),
    )
    icon = pystray.Icon('LivingAssistant', image, 'Living Assistant', menu)
    icon.run()
