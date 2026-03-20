---

name: web\_search

description: Search the web for current information, news, articles, and real-time data. Use when the user asks about current events, latest news, recent developments, or information that may have changed since your training cutoff.

---



\# Web Search Skill



When the user asks for current information, you MUST call the `web\_search` tool. Do NOT output the tool schema.



\## Step 1: Identify the Tool



The tool is called `web\_search`. NOT "search", NOT "google", NOT "duckduckgo".



\## Step 2: Call the Tool with Arguments



You MUST provide the `query` argument. Example:



```json

{

&nbsp; "name": "web\_search",

&nbsp; "arguments": {

&nbsp;   "query": "latest news headlines today"

&nbsp; }

}

```



\## Complete Examples



User: "What are the big headlines today?"

Your response:

```json

{

&nbsp; "name": "web\_search",

&nbsp; "arguments": {

&nbsp;   "query": "major news headlines today"

&nbsp; }

}

```



User: "What's the latest on AI?"

Your response:

```json

{

&nbsp; "name": "web\_search",

&nbsp; "arguments": {

&nbsp;   "query": "latest artificial intelligence news"

&nbsp; }

}

```



User: "Who won the game last night?"

Your response:

```json

{

&nbsp; "name": "web\_search",

&nbsp; "arguments": {

&nbsp;   "query": "sports results yesterday"

&nbsp; }

}

```



\## CRITICAL RULES



1\. `"name"` MUST be exactly: `web\_search`

2\. `"arguments"` MUST have a `"query"` key with a search string

3\. NEVER output the tool schema or description

4\. NEVER call with empty arguments `{}`

5\. Keep queries concise and relevant



