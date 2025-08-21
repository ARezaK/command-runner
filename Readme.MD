# CommandRunner
For running management commands from the web interface

Add to requirements.txt
```
CommandRunner@ git+https://github.com/ARezaK/command-runner.git
```

Copy templates folder to your main app folder


Add to urls.py
```
path('command-runner/', include('command_runner.urls')),
```

Add to INSTALLED_APPS
```
INSTALLED_APPS = [
    ...
    'command_runner',
    ...
]
```

Access via

```
website_url +  /command-runner/
```
