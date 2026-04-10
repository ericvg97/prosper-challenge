
# Decisions
## Product
1. LLM for people disambiguation vs exact match: I was worried about two things. First, that a typo or missing middle name or similar could cause the patient to not be found. Second, that a fraudulent user might try to get data from real patients by giving only partial names like "Eric" or "Smith". The first one could be solved without and LLM with some type of fuzzy match but the second made me worry a bit more. Instead of introducing an OpenAI api call inside the bot itself, we could add it directly in the voice agent to allow it to react accordingly and ask the patient for a complete name.
2. Intermediate nodes in state machine to tell customer that the agent is doing work that could take some time

## Engineering
1. State based conversation vs LLM with tool calls: I chose a graph based approach because the conversation has a clear goal and steps to achieve it. Representing the conversation as a state machine should reduce the hallucinations of the LLM, as we are giving it much more constraint steps. It also reduces the amount of context the LLM needs for every step.
2. Pipeflows vs Implementing the state myself: Pipeflows seems to have everything I needed to model the state machine and in this way I didn't need to model the state, which seemed more simple and extensible in the future, when the state machine will potentially grow a lot when conversations have more goals and steps.
3. Playwright vs GraphQL/API: I chose Playwright because the 0 to 1 is much faster as there is no need to handle cookies, read undocumented api calls and so on. For a production environment where reliability and latency matters I'd give GraphQL a try.
4. Chose gpt-4o-mini for name disambiguation as we would want something super fast, and it is an easy task


# Known issues
## Engineering
1. The voice agent is not tested
2. The playwright bot is not correctly tested (I got some issues with the browser being shared between tests)
3. The playwright bot, in some steps, relies on timeouts instead of more deterministic signals such as api responses
4. In case of a provider (ElevenLabs or OpenAI) being down, the agent would be down.
5. If I were to put playwright in production, I would add more logging (or even taking a screenshot in case of failure), so as to detect easily when the page has change and it is breaking the bot.  
6. No monitoring: To put this agent in production we would require to understand how it is working, for example I would like to know the answer to: How many turns does the conversation take? How many times is there a state transition between this state and this other one? 
7. The browser for playwright could be reused between usages of healthie.py. I removed the singletons to allow for concurrency, even if it means opening a new browser every time. 

## Product
1. The LLM doesn't ask for the details again in case of not finding the patient or not being able to add an appointment. This would require better error handling in the playwright part so that the agent knows if it is an error with the data or with the bot or with healthie. It would also require adding transitions in the state machine to allow to go back to past states in case of the information provided being wrong.
2. Throughout the assignment I have felt that completely dividing the STT and LLM steps loses a lot of information. For instance, if the customer says its name is "Eric Smi***" (where * are unknown characters) the STT will transcribe this to a best guess, let's say "Eric Smidt" and the agent will search for this and find no results if the correct name was "Eric Smith". A human operator would just look for "Eric Smi" (knowing it has not correctly understood the final characters)
3. The agent doesn't account for timezones and doesn't ask for clarifications between AM and PM





# Improvements
## Latency
1. Pre-navigate to the patient page while the agent is asking about appointment details
2. Moving from Playwright to GraphQL

## Reliability
1. Moving to GraphQL
2. Add fallback providers for STT, TTS and LLM
3. Idempotency check when creating an appointment

## Evaluation
1. Create a dataset of 1. LLM voice agents that act as a customer 2. the expected outcome of the conversation with our agent. Each agent from the dataset is prompted in a different way to go through different flow paths (example: "Never say your complete name, only say you are Eric"). Then an LLM as a judge checking the outcome is the desired one (example: "No appointment is created and no customer information is leaked to customer")
2. I would release new versions or models with a FF so as to be able to compare important metrics between previous and current version
3. Use an LLM as a judge of past conversations checking for specific things: was information from other customers leaked, was the customer satisfied, etc. 




