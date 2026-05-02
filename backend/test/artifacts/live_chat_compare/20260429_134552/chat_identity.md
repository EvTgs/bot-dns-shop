# Live Chat Compare

scenario: `chat_identity`

## Turn 1

Prompt: Кто ты в этом боте и чем реально можешь помочь?

### Bot
Я здесь, чтобы помочь с выбором электроники — кидай бюджет или задачу, посоветую лучший вариант. Что ищешь?

### Direct
Я AI-ассистент в этом боте. Могу помочь с ответами на вопросы, советами, поиском информации, решением простых задач или просто поболтать. Если нужно что-то конкретное — спрашивай.

### Metrics
{
  "bot_len": 107,
  "direct_len": 179,
  "bot_has_list": false,
  "direct_has_list": true,
  "bot_mentions_dns": false,
  "direct_mentions_dns": false
}

## Turn 2

Prompt: Ответь короче, одним абзацем, без списка и без официоза.

### Bot
Просто спроси — я помогу с техникой, сравню или посоветую.

### Direct
Я здесь, чтобы быстро отвечать на вопросы, помогать с задачами и просто болтать, если хочешь.

### Metrics
{
  "bot_len": 58,
  "direct_len": 93,
  "bot_has_list": false,
  "direct_has_list": false,
  "bot_mentions_dns": false,
  "direct_mentions_dns": false
}
