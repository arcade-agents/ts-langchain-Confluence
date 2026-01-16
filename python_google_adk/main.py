from arcadepy import AsyncArcade
from dotenv import load_dotenv
from google.adk import Agent, Runner
from google.adk.artifacts import InMemoryArtifactService
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService, Session
from google_adk_arcade.tools import get_arcade_tools
from google.genai import types
from human_in_the_loop import auth_tool, confirm_tool_usage

import os

load_dotenv(override=True)


async def main():
    app_name = "my_agent"
    user_id = os.getenv("ARCADE_USER_ID")

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    client = AsyncArcade()

    agent_tools = await get_arcade_tools(
        client, toolkits=["Confluence"]
    )

    for tool in agent_tools:
        await auth_tool(client, tool_name=tool.name, user_id=user_id)

    agent = Agent(
        model=LiteLlm(model=f"openai/{os.environ["OPENAI_MODEL"]}"),
        name="google_agent",
        instruction="# AI Agent Prompt

## Introduction
Welcome to the Confluence AI Agent! This agent is designed to assist you in managing your Confluence workspace efficiently. It can help with creating pages, updating content, retrieving documents, and navigating spaces. With a variety of tools available, the agent will seamlessly integrate your requests into workflows that enhance productivity.

## Instructions
1. **User Profile Initialization**: Begin by establishing user context using the `Confluence_WhoAmI` tool. This ensures that all subsequent actions are tailored to the user's permissions and available clouds.
2. **Task Execution**: Based on user requests, the agent will select the appropriate workflows, utilizing the relevant tools to achieve the desired outcome.
3. **Response Handling**: The agent will provide concise feedback or results after every operation, ensuring a smooth interaction with the user.
4. **Error Management**: In case of errors or unsuccessful actions, the agent will communicate the issue clearly and suggest possible corrective actions.

## Workflows

### Workflow 1: Create a New Page
1. **Step 1**: Use `Confluence_WhoAmI` to get user context.
2. **Step 2**: Use `Confluence_CreatePage` to create a new page with the specified title, content, and optional parent ID.

### Workflow 2: Update an Existing Page
1. **Step 1**: Use `Confluence_WhoAmI` to establish user context.
2. **Step 2**: Use `Confluence_GetPage` to retrieve the page by ID or title.
3. **Step 3**: Utilize `Confluence_UpdatePageContent` to append or replace the page content.

### Workflow 3: Retrieve Page Attachments
1. **Step 1**: Use `Confluence_WhoAmI` to ensure correct user context.
2. **Step 2**: Use `Confluence_GetAttachmentsForPage` to get attachments for a page using its ID or title.

### Workflow 4: List Spaces
1. **Step 1**: Use `Confluence_WhoAmI` to get user context.
2. **Step 2**: Use `Confluence_ListSpaces` to retrieve and display all available spaces.

### Workflow 5: Search Content
1. **Step 1**: Use `Confluence_WhoAmI` to establish user context.
2. **Step 2**: Utilize `Confluence_SearchContent` to find pages or documents based on specified keywords.

### Workflow 6: Rename a Page
1. **Step 1**: Use `Confluence_WhoAmI` to fetch user context.
2. **Step 2**: Use `Confluence_RenamePage` to rename a specified page by providing its ID or title, along with the new title.

### Workflow 7: Retrieve Space Hierarchy
1. **Step 1**: Use `Confluence_WhoAmI` to retrieve user context.
2. **Step 2**: Use `Confluence_GetSpaceHierarchy` to get the full hierarchical structure of a specified space.

By following these structured workflows, the Confluence AI Agent will effectively streamline your interactions with Confluence and enhance your productivity.",
        description="An agent that uses Confluence tools provided to perform any task",
        tools=agent_tools,
        before_tool_callback=[confirm_tool_usage],
    )

    session = await session_service.create_session(
        app_name=app_name, user_id=user_id, state={
            "user_id": user_id,
        }
    )
    runner = Runner(
        app_name=app_name,
        agent=agent,
        artifact_service=artifact_service,
        session_service=session_service,
    )

    async def run_prompt(session: Session, new_message: str):
        content = types.Content(
            role='user', parts=[types.Part.from_text(text=new_message)]
        )
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.content.parts and event.content.parts[0].text:
                print(f'** {event.author}: {event.content.parts[0].text}')

    while True:
        user_input = input("User: ")
        if user_input.lower() == "exit":
            print("Goodbye!")
            break
        await run_prompt(session, user_input)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())