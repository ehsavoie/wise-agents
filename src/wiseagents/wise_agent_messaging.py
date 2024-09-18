import logging
from abc import *
from enum import StrEnum
from typing import Callable, Optional

import yaml
from yaml import YAMLObject
from yaml.resolver import BaseResolver


class WiseAgentMessageType(StrEnum):
    ACK = "ACK"
    ALERT = "ALERT"
    CANNOT_ANSWER = "CANNOT_ANSWER"
    QUERY = "QUERY"
    RESPONSE = "RESPONSE"
    ACTION_REQUEST = "ACTION_REQUEST"
    HUMAN = "HUMAN"

class WiseAgentEvent:
    """
    TODO
    """

def wiseAgentMessageType_representer(dumper, data):
    return dumper.represent_scalar(BaseResolver.DEFAULT_SCALAR_TAG, str(data.value))


class WiseAgentMessage(YAMLObject):
    ''' A message that can be sent between agents. '''
    yaml_tag = u'!wiseagents.WiseAgentMessage'
    def __init__(self, message: str, sender: Optional[str] = None, message_type: Optional[WiseAgentMessageType] = None, 
                 chat_id: Optional[str] = None, tool_id : Optional[str] = None, context_name: Optional[str] = None,
                 route_response_to: Optional[str] = None):
        '''Initialize the message.

        Args:
            message (str): the message contents (a natural language string)
            sender Optional(str): the sender of the message (or None if the sender was not specified)
            message_type Optional(WiseAgentMessageType): the type of the message (or None if the type was not specified)
            chat_id Optional(str): the id of the message
            tool_id Optional(str): the id of the tool
            context_name Optional(str): the context name of the message
            route_response_to Optional(str): the id of the tool to route the response to
            ''' 
        self._message = message
        self._sender = sender
        self._message_type = message_type
        self._chat_id = chat_id
        self._tool_id = tool_id
        self._route_response_to = route_response_to
        if context_name is not None:
            self._context_name = context_name
        else:
            self._context_name = 'default'
        self.__class__.yaml_dumper.add_representer(WiseAgentMessageType, wiseAgentMessageType_representer)

    def __setstate__(self, state):
        self._message = state["_message"]
        self._sender =  state["_sender"]
        self._message_type = WiseAgentMessageType(state["_message_type"])
        self._chat_id =  state["_chat_id"]
        self._tool_id =  state["_tool_id"]
        self._route_response_to =  state["_route_response_to"]
        if  state["_context_name"] is not None:
            self._context_name = state["_context_name"]
        else:
            self._context_name = 'default'


    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message}, sender={self.sender}, message_type={self.message_type}, id={self.chat_id}, tool_id={self.tool_id}, context_name={self.context_name}, route_response_to={self.route_response_to}, route_response_to={self.route_response_to})"

    @property
    def context_name(self) -> str:
        """Get the context name of the message."""
        return self._context_name
    
    @property
    def message(self) -> str:
        """Get the message contents (a natural language string)."""
        return self._message

    @property
    def sender(self) -> str:
        """Get the sender of the message (or None if the sender was not specified)."""
        return self._sender
    @sender.setter
    def sender(self, sender: str):
        '''Set the sender of the message.

        Args:
            sender (str): the sender of the message
        '''
        self._sender = sender
    
    @property
    def message_type(self) -> WiseAgentMessageType:
        """Get the type of the message (or None if the type was not specified)."""
        return self._message_type
    @property
    def chat_id(self) -> str:
        """Get the id of the message."""
        return self._chat_id
    
    @property
    def tool_id(self) -> str:
        """Get the id of the tool."""
        return self._tool_id
    
    @property
    def route_response_to(self) -> str:
        """Get the id of the tool."""
        return self._route_response_to

class WiseAgentTransport(YAMLObject):
    
    ''' A transport for sending messages between agents. '''    
    def set_call_backs(self, request_receiver: Optional[Callable[[], WiseAgentMessage]] = None,
                 event_receiver: Optional[Callable[[], WiseAgentEvent]] = None,
                 error_receiver: Optional[Callable[[], WiseAgentMessage]] = None,
                 response_receiver: Optional[Callable[[], WiseAgentMessage]] = None):
        '''Set the call back functions for the transport.

        Args:
            request_receiver Optional(Callable[[], WiseAgentMessage]): the call back function for receiving requests
            event_receiver Optional(Callable[[], WiseAgentEvent]): the call back function for receiving events
            error_receiver Optional(Callable[[], WiseAgentMessage]): the call back function for receiving errors
            response_receiver Optional(Callable[[], WiseAgentMessage]): the call back function for receiving responses
        '''
        self._request_receiver = request_receiver
        self._event_receiver = event_receiver
        self._error_receiver = error_receiver
        self._response_receiver = response_receiver
       
    @abstractmethod
    def start(self):
        """
        Start the transport.
        """
        pass
    
    @abstractmethod
    def send_request(self, message: WiseAgentMessage, dest_agent_name: str):
        """
        Send a request message to an agent.


        Args:
            message (WiseAgentMessage): the message to send
        """
        pass
    
    @abstractmethod
    def send_response(self, message: WiseAgentMessage, dest_agent_name: str):
        """
        Send a request message to an agent.


        Args:
            message (WiseAgentMessage): the message to send
        """
        pass
    
    @abstractmethod
    def stop(self):
        """
        Stop the transport.
        """
        pass
    
    @property
    def request_receiver(self) -> Optional[Callable[[], WiseAgentMessage]]:
        """Get the message receiver callback."""
        return self._request_receiver
    
    @property
    def event_receiver(self) -> Optional[Callable[[], WiseAgentEvent]]:
        """Get the event receiver callback."""
        return self._event_receiver
    
    @property
    def error_receiver(self) -> Optional[Callable[[], WiseAgentMessage]]:
        """Get the error receiver callback."""
        return self._error_receiver
    
    @property
    def response_receiver(self) -> Optional[Callable[[], WiseAgentMessage]]:
        """Get the response receiver callback."""
        return self._response_receiver
    
    
    
