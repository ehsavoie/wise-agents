import logging
import os
import io
import pickle
from _curses import use_env
from time import sleep

import pytest
import yaml

from wiseagents import WiseAgent, WiseAgentMessage, WiseAgentRegistry
from wiseagents.transports import StompWiseAgentTransport
from wiseagents.yaml import WiseAgentsLoader


@pytest.fixture(scope="session", autouse=True)
def run_after_all_tests():
    yield
    
    

class WiseAgentDoingNothing(WiseAgent):
     
    request_received : WiseAgentMessage = None
    response_received : WiseAgentMessage = None
    transport_agent_name: str = ''
    
    def __init__(self, name: str, description: str, transport_agent_name: str):
        self._name = name
        self.transport_agent_name = transport_agent_name;
        self.transport_agent_name = transport_agent_name;
        self._description = description
        transport = StompWiseAgentTransport(host='localhost', port=61616, transport_agent_name=self.transport_agent_name)
        super().__init__(name, description, transport, None, None, None)
        
        
    def process_event(self, event):
        return True
    def process_error(self, error):
        logging.error(error)
        return True
    def handle_request(self, request: WiseAgentMessage):
        self.request_received = request
        logging.info("Received request from " + request.sender)
        self.send_response(WiseAgentMessage('I am doing nothing since I received ' + request.message, self.name), request.sender )
        return True
    def process_response(self, response : WiseAgentMessage):
        self.response_received = response
        return True
    def get_recipient_agent_name(self, message):
        return self.transport_agent_name
    def stop(self):
        self.transport.stop()
        WiseAgentRegistry.unregister_agent(self.name)
    


#@pytest.mark.skip(reason="This works fine when run on its own, but fails when run with all the other tests")
def test_send_message_to_agent_and_get_response():
    os.environ['STOMP_USER'] = 'artemis'
    os.environ['STOMP_PASSWORD'] = 'artemis'

    useRedis = WiseAgentRegistry.get_config()['use_redis']
    logging.debug(f'******************* Using Redis: {useRedis}')
    agent1 = WiseAgentDoingNothing('Agent1', 'Agent1', transport_agent_name="WiseIntelligentAgentQueue")
    agent2 = WiseAgentDoingNothing('Agent2', 'Agent2', transport_agent_name="AssistantAgent")
    agent3 = WiseAgentDoingNothing('Agent3', 'Agent3', transport_agent_name="WiseIntelligentAgentQueue")
    agent1.send_request(WiseAgentMessage(message='Do Nothing from Agent1', sender='WiseIntelligentAgentQueue'), dest_agent_name='AssistantAgent')
    sleep(1)
    agent2.send_request(WiseAgentMessage(message='Do Nothing from Agent2', sender='AssistantAgent'), dest_agent_name='WiseIntelligentAgentQueue')
    sleep(1)
    agent2.send_request(WiseAgentMessage(message='Do Nothing Again from Agent2', sender='AssistantAgent'), dest_agent_name='WiseIntelligentAgentQueue')
    sleep(1)

    assert agent2.request_received.message == 'Do Nothing from Agent1'
    if agent1 != None and agent1.response_received.message != None:
        logging.info("Agent 1 response:" + agent1.response_received.message)
    assert agent1.response_received.message == 'I am doing nothing since I received Do Nothing from Agent1'

    exchangedMessages = list()
    message: WiseAgentMessage
    if not useRedis:
        for  message in WiseAgentRegistry.get_or_create_context('default').message_trace:
            messageAsString = dict()
            messageAsString['message'] = message.message
            messageAsString['sender'] = message.sender
            logging.debug(f'******************* Message: {message}')
            exchangedMessages.append(messageAsString)
    else:
        for messageAsString in WiseAgentRegistry.get_or_create_context('default').message_trace:
            message = WiseAgentMessage.str_to_dict(messageAsString.decode("utf-8"))
            logging.debug(f'############ Message: {message}')
            exchangedMessages.append(message)

    assert exchangedMessages[0]['message'] == 'Do Nothing from Agent1'
    assert exchangedMessages[0]['sender'] == 'WiseIntelligentAgentQueue'
    assert exchangedMessages[1]['message'] == 'I am doing nothing since I received Do Nothing from Agent1'
    assert exchangedMessages[1]['sender'] == 'Agent2'
    assert exchangedMessages[2]['message'] == 'Do Nothing from Agent2'
    assert exchangedMessages[2]['sender'] == 'AssistantAgent'
    assert exchangedMessages[3]['message'] == 'I am doing nothing since I received Do Nothing from Agent2'
    assert exchangedMessages[3]['sender'] == 'Agent1'
    assert exchangedMessages[4]['message'] == 'Do Nothing Again from Agent2'
    assert exchangedMessages[4]['sender'] == 'AssistantAgent'
    assert exchangedMessages[5]['message'] == 'I am doing nothing since I received Do Nothing Again from Agent2'
    assert exchangedMessages[5]['sender'] == 'Agent3'

    for participant in WiseAgentRegistry.get_or_create_context('default').participants :
        logging.debug(f'*******************Participant: {participant}')

    assert WiseAgentRegistry.get_or_create_context('default').participants.__len__() == 3
    assert WiseAgentRegistry.get_or_create_context('default').participants[0].decode("utf-8") == 'Agent1'
    assert WiseAgentRegistry.get_or_create_context('default').participants[1].decode("utf-8") == 'Agent2'
    assert WiseAgentRegistry.get_or_create_context('default').participants[2].decode("utf-8") == 'Agent3'

    #stop all agents
    agent1.stop()
    agent2.stop()
    agent3.stop()
    WiseAgentRegistry.get_or_create_context('default').participants.clear()
    WiseAgentRegistry.get_or_create_context('default').message_trace.clear()
    WiseAgentRegistry.remove_context('default')

    def str_to_dict(string):
        # remove the curly braces from the string
        string = string.strip('WiseAgentMessage()')

        # split the string into key-value pairs
        pairs = string.split(', ')

        # use a dictionary comprehension to create
        # the dictionary, converting the values to
        # integers and removing the quotes from the keys
        return {key[1:-2]: int(value) for key, value in (pair.split('=') for pair in pairs)}
    