# Direct API observations

All paths target `http://10.0.0.21:8000`. Times are milliseconds for the entire request.

## api

| Path | HTTP | ms | Shape | Count |
| --- | --- | --- | --- | --- |
| `/health` | 200 | 8.6 | object | — |
| `/api/v1/status` | 200 | 24.9 | object | — |
| `/api/v1/matches/results` | 200 | 3.1 | array | 50 |
| `/api/v1/matches/upcoming` | 200 | 2.7 | array | 30 |
| `/api/v1/matches/live` | 200 | 1.9 | array | 0 |
| `/api/v1/rankings` | 200 | 4.3 | array | 128 |
| `/api/v1/stats?region=na&timespan=all` | 200 | 7.1 | envelope | 100 |
| `/api/v1/news` | 200 | 2.4 | array | 30 |
| `/api/v1/events` | 200 | 142.1 | array | 70 |
| `/api/v1/teams` | 200 | 3.2 | envelope | 0 |
| `/api/v1/players` | 200 | 1.8 | envelope | 0 |
| `/api/v1/match/753445` | 200 | 5.9 | object | — |
| `/api/v1/team/8877` | 200 | 182.8 | object | — |
| `/api/v1/player/36245` | 200 | 2370.8 | object | — |

## followup

| Path | HTTP | ms | Shape | Count |
| --- | --- | --- | --- | --- |
| `/api/v1/status` | 200 | 26.9 | object | — |
| `/api/v1/player/36245` | 200 | 3.0 | object | — |
| `/api/v1/team/8877` | 200 | 2.4 | object | — |
| `/api/v1/trends/player/36245` | 200 | 14.4 | object | — |
| `/api/v1/players/36245/dimensions?region=na&timespan=all` | 200 | 3.4 | object | — |
| `/api/v1/trends/team/8877` | 200 | 18.4 | object | — |
| `/api/v1/history/player/36245?limit=3` | 200 | 15.9 | array | 3 |
| `/api/v1/players?q=N4RRATE` | 200 | 610.1 | envelope | 1 |
| `/api/v1/teams?q=Karmine%20Corp` | 200 | 14.8 | envelope | 2 |

## final

| Path | HTTP | ms | Shape | Count |
| --- | --- | --- | --- | --- |
| `/health` | 200 | 6.5 | object | — |
| `/api/v1/status` | 200 | 32.0 | object | — |
| `/api/v1/match/753445` | 200 | 5.9 | object | — |
| `/api/v1/player/36245` | 200 | 2.6 | object | — |
| `/api/v1/trends/player/36245` | 200 | 8.5 | object | — |
| `/api/v1/history/player/36245?limit=3` | 200 | 6.9 | array | 3 |
| `/api/v1/players/36245/dimensions?region=na&timespan=all` | 200 | 3.7 | object | — |
| `/api/v1/players?q=N4RRATE` | 200 | 19.2 | envelope | 1 |
| `/api/v1/teams?q=Karmine%20Corp` | 200 | 5.9 | envelope | 2 |
