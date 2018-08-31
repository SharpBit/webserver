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
<br>
Note: `/hq/answer` and `/hq/question` both require an API Key to POST to in order to maintain correct question info.
## POST request format
Here's an example JSON to post to `/hq/question`:
```json
{
    "question": "Which of these is the name of a common game for kids?",
    "questionNumber": 1,
    "time": 1535591069.6430561543,
    "category": "Games"
}
```
Here's an example JSON that would work with `/hq/answer`:
```json
{
    "question": "Which of these is the name of a common game for kids?",
    "answers": [
        {
            "answer": "Sloth in the Slagheap",
            "correct": false,
            "count": 3505
        },
        {
            "answer": "Anteater in the Alley",
            "correct": false,
            "count": 4658
        },
        {
            "answer": "Monkey in the Middle",
            "correct": true,
            "count": 360943
        }
    ],
    "final": false
}
```
`false` means that it isn't the quiz's final question. If it's question 12/12, then `final` should be `true`
