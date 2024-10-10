import argparse
import importlib
import logging
import signal
import sys
import threading
import traceback
from typing import List
import uuid
from wiseagents.yaml import WiseAgentsLoader

import yaml

from wiseagents import WiseAgent, WiseAgentMessage, WiseAgentRegistry
# These unsued imports are need for yaml.load_all. If they are removed, the yaml.load_all will not find the constructors for these classes
import wiseagents.agents
from wiseagents.transports import StompWiseAgentTransport

cond = threading.Condition()

global _passThroughClientAgent1

def response_delivered(message: WiseAgentMessage):
    with cond: 
        response = message.message
        msg = response
        print(f"C Response delivered: {msg}")
        cond.notify()

def signal_handler(sig, frame):
    global agent_list
    global context_name
    print('You pressed Ctrl+C! Please wait for the agents to stop')
    for agent in agent_list:
        print(f"Stopping agent {agent.name}")
        agent.stop_agent()
    print(f"Removing context {context_name}")
    WiseAgentRegistry.remove_context(context_name)
    exit(0)


    

def main():
    global agent_list
    global context_name
    agent_list = []
    user_input = "h"
    file_path = None
    default_file_path = "src/wiseagents/cli/test-multiple.yaml"

    parser = argparse.ArgumentParser(prog="Wise Agent Argument Parser", description="Wise Agent CLI to run and manage Wise Agents", add_help=True)
    parser.add_argument("filename", nargs="?", help="is optional. If provided, the CLI will automatically load agents from the specified YAML file upon startup.")
    parser.add_argument("--debug", dest="debug", help="Setting the logging level to DEBUG instead of INFO", type=bool, default=False)
    args = parser.parse_args()
    logger = logging.getLogger(__name__)
    if (args.debug):
        level=logging.DEBUG
    else:
        level=logging.INFO
    logging.basicConfig(filename='./log/agents.log', filemode="w",
                        format='%(asctime)s %(levelname)s [%(name)s]: %(message)s', encoding='utf-8',
                        level=level)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

    logger.info(f"Starting CLI in debug mode {args.debug} with file {args.filename}")
    signal.signal(signal.SIGINT, signal_handler)
    context_name = "CLI." + str(uuid.uuid4())
    WiseAgentRegistry.create_context(context_name)
    if (args.filename is not None):
        user_input="/load-agents"
        file_path=args.filename
        logger.info(f"Loading agents from {file_path}")
    else:
        logger.info(f"No agent from {file_path}")

    while True:
        if  (user_input == '/help' or user_input == '/h'):
            print('/(l)oad-agents: Load agents from file')
            print('/(r)eload agents: Reload agents from file')
            print('/(c)hat: Start a chat')
            print('/(t)race: Show the message trace')
            print('/e(x)it: Exit the application')
            print('/(h)elp: Show the available commands')
            print('(a)gents: Show the registered agents')
            print('(s)end: Send a message to an agent')
            
        if (user_input == '/trace' or user_input == '/t'):
            for msg in WiseAgentRegistry.get_context(context_name).message_trace:
                print(msg)
        if  (user_input == '/exit' or user_input == '/x'):
            #stop all agents
            print('/exit selected! Please wait for the agents to stop')
            for agent in agent_list:
                print(f"Stopping agent {agent.name}")
                agent.stop_agent()
            print(f"Removing context {context_name}")
            WiseAgentRegistry.remove_context(context_name)
            sys.exit(0)
        if (user_input == '/reload-agents' or user_input == '/r'):
            for agent in agent_list:
                agent.stop_agent()
            reload_path = input(f'Enter the file path (ENTER for default {file_path} ): ')
            if reload_path:
                file_path = reload_path
            user_input = '/load-agents'
        if (user_input == '/load-agents' or user_input == '/l'):
            if not file_path:
                file_path = input(f'Enter the file path (ENTER for default {default_file_path} ): ')
                if not file_path:
                    file_path = default_file_path
            with open(file_path) as stream:
                try:

                    for agent in yaml.load_all(stream, Loader=WiseAgentsLoader):
                        agent : WiseAgent
                        logger.info(f'Loaded agent: {agent.name}')
                        if agent.name == "PassThroughClientAgent1":
                            _passThroughClientAgent1 = agent
                            _passThroughClientAgent1.set_response_delivery(response_delivered)
                        agent.start_agent()
                        agent_list.append(agent)
                except yaml.YAMLError as exc:
                    traceback.print_exc()
                lines = [f'{key} {value}' for key, value in WiseAgentRegistry.fetch_agents_metadata_dict().items()]
                print(f"registered agents=\n {'\n'.join(lines)}")
        if  (user_input == '/chat' or user_input == '/c'):
            while True:
                user_input = input("Enter a message (or /back): ")
                if  (user_input == '/back'):
                    break
                with cond:
                    _passThroughClientAgent1.send_request(WiseAgentMessage(message=user_input, sender="PassThroughClientAgent1", context_name=context_name), "LLMOnlyWiseAgent2")
                    cond.wait()
        if (user_input == '/agents' or user_input == '/a'):
            lines = [f'{key} {value}' for key, value in WiseAgentRegistry.fetch_agents_metadata_dict().items()]
            print(f"registered agents=\n {'\n'.join(lines)}")

        if (user_input == '/send' or user_input == '/s'):
            agent_name = input("Enter the agent name: ")
            message = input("Enter the message: ")
            agent : WiseAgent = WiseAgentRegistry.get_agent_metadata(agent_name)
            if agent:
                with cond:
                    _passThroughClientAgent1.send_request(WiseAgentMessage(message=message, sender="PassThroughClientAgent1", context_name=context_name), agent_name)
                    cond.wait()
            else:
                print(f"Agent {agent_name} not found")
        user_input = input("wise-agents (/help for available commands): ")
        
    


if __name__ == "__main__":
    main()
