import logging
import os
from time import sleep

import pytest

from wiseagents import WiseAgent, WiseAgentMessage, WiseAgentRegistry
from wiseagents.transports import StompWiseAgentTransport


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
        pass    
    


#@pytest.mark.skip(reason="This works fine when run on its own, but fails when run with all the other tests")
def test_send_message_to_agent_and_get_response():
    os.environ['STOMP_USER'] = 'artemis'
    os.environ['STOMP_PASSWORD'] = 'artemis'

    agent1 = WiseAgentDoingNothing('Agent1', 'Agent1', transport_agent_name="WiseIntelligentAgentQueue")
    agent2 = WiseAgentDoingNothing('Agent2', 'Agent2', transport_agent_name="AssistantAgent")
    agent3 = WiseAgentDoingNothing('Agent3', 'Agent3', transport_agent_name="WiseIntelligentAgentQueue")
    try:
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

        for  message in WiseAgentRegistry.get_or_create_context('default').message_trace:
            logging.debug(f'******************* {message}')

        assert WiseAgentRegistry.get_or_create_context('default').message_trace[0].message == 'Do Nothing'
        assert WiseAgentRegistry.get_or_create_context('default').message_trace[0].sender == 'Agent1'
        assert WiseAgentRegistry.get_or_create_context('default').message_trace[1].message == 'I am doing nothing'
        assert WiseAgentRegistry.get_or_create_context('default').message_trace[1].sender == 'Agent2'
        assert WiseAgentRegistry.get_or_create_context('default').message_trace[2].message == 'Do Nothing'
        assert WiseAgentRegistry.get_or_create_context('default').message_trace[2].sender == 'Agent2'
        assert WiseAgentRegistry.get_or_create_context('default').message_trace[3].message == 'I am doing nothing'
        assert WiseAgentRegistry.get_or_create_context('default').message_trace[3].sender == 'Agent1'

        assert WiseAgentRegistry.get_or_create_context('default').participants.__len__() == 2
        assert WiseAgentRegistry.get_or_create_context('default').participants[0].name == 'Agent1'
        assert WiseAgentRegistry.get_or_create_context('default').participants[1].name == 'Agent2'

    #stop all agents
    finally:
        agent1.stop()
        agent2.stop()
        agent3.stop()

    
    