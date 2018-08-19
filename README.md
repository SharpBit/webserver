# HQ Trivia Webserver
A simple python sanic [webserver](http://sharpbit-webserver.herokuapp.com/) made for [HQ Trivia](https://en.wikipedia.org/wiki/HQ_Trivia/).<br>

## Endpoints
Endpoint | Function | Type
-------- | -------- | ----
`/` | Test Page | GET
`/status/<status>` | Get info about a status code | GET
`/hq` | Info about HQ endpoints | GET
`/hq/question` | Post question info | POST
`/hq/answer` | Post an answer to a question | POST
`/hq/questions` | List of HQ Questions | GET
Note: `/hq/answer` and `/hq/question` both require an API Key to POST to in order to maintain correct question info.
## POST request format
Here's an example JSON to post to `/hq/question`:
```json
{
    "question": "What animal has the largest eyes in the animal kingdom?",
    "answers": [
        "Giant Pacific octopus",
        "Giant squid",
        "Blue whale"
    ],
    "questionNumber": 9,
    "time": 1534640999.2183766,
    "category": "Nature"
}
```
Here's an example JSON that would work with `/hq/answer`:
```json
{
    "question": "What animal has the largest eyes in the animal kingdom?",
    "answer": 2,
    "final": false
}
```
`false` means that it isn't the quiz's final question.
