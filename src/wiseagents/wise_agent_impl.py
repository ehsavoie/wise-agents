import json
import logging
from typing import Callable, List, Optional
import uuid

from openai import NOT_GIVEN
from openai.types.chat import ChatCompletionToolParam
from pydantic import BaseModel

from wiseagents.graphdb import WiseAgentGraphDB

from wiseagents.vectordb import Document, WiseAgentVectorDB

from wiseagents import WiseAgent, WiseAgentMessage, WiseAgentMessageType, WiseAgentRegistry, WiseAgentTransport, \
    WiseAgentTool
from wiseagents.llm import WiseAgentLLM

CONFIDENCE_SCORE_THRESHOLD = 85
MAX_ITERATIONS_FOR_COORDINATOR = 5
CANNOT_ANSWER = "I don't know the answer to the query."

class PassThroughClientAgent(WiseAgent):
    '''This agent is used mainly for test purposes. It just passes the request to another agent and sends back the response to the client.'''
    '''Use Stomp protocol'''
    yaml_tag = u'!wiseagents.PassThroughClientAgent'
    def __init__(self, name, description , transport):
        '''Initialize the agent.
        
        Args:
            name (str): the name of the agent
            description (str): a description of the agent
            transport (WiseAgentTransport): the transport to use for communication'''
        
        self._name = name
        super().__init__(name=name, description=description, transport=transport, llm=None)
    def __repr__(self):
        '''Return a string representation of the agent.'''
        return f"{self.__class__.__name__}(name={self.name}, description={self.description})"
    def process_request(self, request):
        '''Process a request message just passing it to the another agent.'''
        self.send_request(WiseAgentMessage(request, self.name), 'WiseIntelligentAgent' )
        return True
    def process_response(self, response):
        '''Process a response message just sending it back to the client.'''
        self.response_delivery(response)
        return True
    def process_event(self, event):
        '''Do nothing'''
        return True
    def process_error(self, error):
        '''Do nothing'''
        return True
    def get_recipient_agent_name(self, message):
        '''Return the name of the agent to send the message to.'''
        return self.name
    def stop(self):
        '''Do nothing'''
        pass
    @property
    def name(self) -> str:
        """Get the name of the agent."""
        return self._name
    @property
    def response_delivery(self) -> Optional[Callable[[], WiseAgentMessage]]:
        '''Get the function to deliver the response to the client.
        return (Callable[[], WiseAgentMessage]): the function to deliver the response to the client'''
        return self._response_delivery
    def set_response_delivery(self, response_delivery: Callable[[], WiseAgentMessage]):
        '''Set the function to deliver the response to the client.
        
        Args:
            response_delivery (Callable[[], WiseAgentMessage]): the function to deliver the response to the client'''
        self._response_delivery = response_delivery
class LLMOnlyWiseAgent(WiseAgent):
    '''This agent implementation is used to test the LLM only agent.'''
    '''Use Stomp protocol''' 
    yaml_tag = u'!wiseagents.LLMOnlyWiseAgent'
    def __init__(self, name: str, description: str, llm : WiseAgentLLM, trasport: WiseAgentTransport):
        '''Initialize the agent.

        Args:
            name (str): the name of the agent
            description (str): a description of the agent
            llm (WiseAgentLLM): the LLM agent to use for processing requests
            transport (WiseAgentTransport): the transport to use for communication'''
        self._name = name
        self._description = description
        self._transport = trasport
        llm_agent = llm
        super().__init__(name=name, description=description, transport=self.transport, llm=llm_agent)

    def __repr__(self):
        '''Return a string representation of the agent.'''
        return f"{self.__class__.__name__}(name={self.name}, description={self.description}, llm={self.llm}, transport={self.transport})"
        
    def process_event(self, event):
        '''Do nothing'''
        return True
    def process_error(self, error):
        '''Log the error and return True.'''
        logging.error(error)
        return True
    def process_request(self, request: WiseAgentMessage):
        '''Process a request message by passing it to the LLM agent and sending the response back to the client.

        Args:
            request (WiseAgentMessage): the request message to process'''
        llm_response = self.llm.process_single_prompt(request.message)
        self.send_response(WiseAgentMessage(message=llm_response.content, sender=self.name, context_name=request.context_name, chat_id=request.chat_id), request.sender )
        return True
    def process_response(self, response : WiseAgentMessage):
        '''Do nothing'''
        return True
    def get_recipient_agent_name(self, message):
        '''Return the name of the agent to send the message to.

        Args:
            message (WiseAgentMessage): the message to process'''
        return self.name
    def stop(self):
        pass    
    @property
    def name(self) -> str:
        """Get the name of the agent."""
        return self._name


    
    

class LLMWiseAgentWithTools(WiseAgent):
    '''This agent implementation is used to test the LLM agent providing a simple tool.'''
    '''Use Stomp protocol''' 
    yaml_tag = u'!wiseagents.LLMWiseAgentWithTools'
    def __init__(self, name: str, description: str, llm : WiseAgentLLM, transport: WiseAgentTransport, tools: List[str]):
        '''Initialize the agent.

        Args:
            name (str): the name of the agent
            description (str): a description of the agent
            llm (WiseAgentLLM): the LLM agent to use for processing requests
            transport (WiseAgentTransport): the transport to use for communication'''
        self._name = name
        self._description = description
        self._transport = transport
        llm_agent = llm
        self._tools = tools
        super().__init__(name=name, description=description, transport=self.transport, llm=llm_agent)

    def __repr__(self):
        '''Return a string representation of the agent.'''
        return f"{self.__class__.__name__}(name={self.name}, description={self.description}, llm={self.llm}, transport={self.transport})"
        
    def process_event(self, event):
        '''Do nothing'''
        return True
    def process_error(self, error):
        '''Log the error and return True.'''
        logging.error(error)
        return True
    def process_request(self, request: WiseAgentMessage):
        '''Process a request message by passing it to the LLM agent and sending the response back to the client.
        It invoke also the tool if required. Tool could be a callback function or another agent.

        Args:
            request (WiseAgentMessage): the request message to process'''
        logging.debug(f"IA Request received: {request}")
        chat_id= str(uuid.uuid4())
        ctx = WiseAgentRegistry.get_or_create_context(request.context_name)
        ctx.append_chat_completion(chat_uuid=chat_id, messages= {"role": "system", "content": self.llm.system_message})
        ctx.append_chat_completion(chat_uuid=chat_id, messages= {"role": "user", "content": request.message})
        
        for tool in self._tools:
            ctx.append_available_tool_in_chat(chat_uuid=chat_id, tools=WiseAgentRegistry.get_tool(tool).get_tool_OpenAI_format())
            
        logging.debug(f"messages: {ctx.llm_chat_completion[chat_id]}, Tools: {ctx.get_available_tools_in_chat(chat_uuid=chat_id)}")    
        llm_response = self.llm.process_chat_completion(ctx.llm_chat_completion[chat_id], ctx.get_available_tools_in_chat(chat_uuid=chat_id))
        
        ##calling tool
        response_message = llm_response.choices[0].message
        tool_calls = response_message.tool_calls
        logging.debug(f"Tool calls: {tool_calls}")
        logging.debug(f"Response message: {response_message}")
        # Step 2: check if the model wanted to call a function
        if tool_calls is not None:
            # Step 3: call the function
            # TODO: the JSON response may not always be valid; be sure to handle errors
            ctx.append_chat_completion(chat_uuid=chat_id, messages= response_message)  # extend conversation with assistant's reply
            
            # Step 4: send the info for each function call and function response to the model
            for tool_call in tool_calls:
                #record the required tool call in the context/chatid
                ctx.append_required_tool_call(chat_uuid=chat_id, tool_name=tool_call.function.name)
                
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                wise_agent_tool : WiseAgentTool = WiseAgentRegistry.get_tool(function_name)
                if wise_agent_tool.is_agent_tool:
                    #call the agent with correlation ID and complete the chat on response
                    self.send_request(WiseAgentMessage(message=tool_call.function.arguments, sender=self.name, 
                                                       chat_id=chat_id, tool_id=tool_call.id, context_name=request.context_name,
                                                       route_response_to=request.sender), 
                                      dest_agent_name=function_name)
                else:
                    function_args = json.loads(tool_call.function.arguments)
                    function_response = wise_agent_tool.exec(**function_args)
                    logging.debug(f"Function response: {function_response}")
                    ctx.append_chat_completion(chat_uuid=chat_id, messages= 
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": function_response,
                        }
                    )  # extend conversation with function response
                    ctx.remove_required_tool_call(chat_uuid=chat_id, tool_name=tool_call.function.name)
            
        
        #SEND THE RESPONSE IF NOT ASYNC, OTHERWISE WE WILL DO LATER IN PROCESS_RESPONSE
        if ctx.get_required_tool_calls(chat_uuid=chat_id) == []: # if all tool calls have been completed (no asynch needed)
            llm_response = self.llm.process_chat_completion(ctx.llm_chat_completion[chat_id], 
                                                            ctx.get_available_tools_in_chat(chat_uuid=chat_id))
            response_message = llm_response.choices[0].message
            logging.debug(f"sending response {response_message.content} to: {request.sender}")
            self.send_response(WiseAgentMessage(response_message.content, self.name), request.sender )
            ctx.llm_chat_completion.pop(chat_id)
            return True
    def process_response(self, response : WiseAgentMessage):
        '''Process a response message and sending the response back to the client.
        It invoke also the tool if required. Tool could be a callback function or another agent.

        Args:
            response (WiseAgentMessage): the response message to process
            '''
        print(f"Response received: {response}")
        chat_id = response.chat_id
        ctx = WiseAgentRegistry.get_or_create_context(response.context_name)
        ctx.append_chat_completion(chat_uuid=chat_id, messages= 
            {
                "tool_call_id": response.tool_id,
                "role": "tool",
                "name": response.sender,
                "content": response.message,
            }
        )  # extend conversation with function response
        ctx.remove_required_tool_call(chat_uuid=chat_id, tool_name=response.sender)
            
        if ctx.get_required_tool_calls(chat_uuid=chat_id) == []: # if all tool calls have been completed (no asynch needed)
            llm_response = self.llm.process_chat_completion(ctx.llm_chat_completion[chat_id], 
                                                            ctx.get_available_tools_in_chat(chat_uuid=chat_id))
            response_message = llm_response.choices[0].message
            logging.debug(f"sending response {response_message.content} to: {response.route_response_to}")
            self.send_response(WiseAgentMessage(response_message.content, self.name), response.route_response_to )
            ctx.llm_chat_completion.pop(chat_id)
            return True
    def get_recipient_agent_name(self, message):
        '''Return the name of the agent to send the message to.

        Args:
            message (WiseAgentMessage): the message to process'''
        return self.name
    def stop(self):
        '''Do nothing'''
        pass    
    @property
    def name(self) -> str:
        """Get the name of the agent."""
        return self._name



class RAGWiseAgent(WiseAgent):
    """
    This agent implementation is used to test the RAG agent.
    Use Stomp protocol
    """
    yaml_tag = u'!wiseagents.RAGWiseAgent'

    def __init__(self, name: str, description: str, llm: WiseAgentLLM, vector_db: WiseAgentVectorDB,
                 transport: WiseAgentTransport, collection_name: Optional[str] = "wise-agents-collection"):
        '''Initialize the agent.

        Args:
            name (str): the name of the agent
            description (str): a description of the agent
            llm (WiseAgentLLM): the LLM agent to use for processing requests
            vector_db (WiseAgentVectorDB): the vector database to use for retrieving documents
            transport (WiseAgentTransport): the transport to use for communication
            collection_name Optional(str): the name of the collection to use for retrieving documents'''
        self._name = name
        self._description = description
        self._transport = transport
        self._vector_db = vector_db
        self._collection_name = collection_name
        llm_agent = llm
        super().__init__(name=name, description=description, transport=self.transport, llm=llm_agent,
                         vector_db=vector_db, collection_name=collection_name)

    def __repr__(self):
        """Return a string representation of the agent."""
        return (f"{self.__class__.__name__}(name={self.name}, description={self.description}, llm={self.llm},"
                f"vector_db={self.vector_db}, collection_name={self.collection_name}, transport={self.transport})")

    def process_event(self, event):
        '''Do nothing'''
        return True

    def process_error(self, error):
        '''Log the error and return True.'''
        logging.error(error)
        return True

    def process_request(self, request: WiseAgentMessage):
        '''Process a request message by passing it to the RAG agent and sending the response back to the client.

        Args:
            request (WiseAgentMessage): the request message to process'''
        retrieved_documents = self.vector_db.query([request.message], self.collection_name, 4)
        llm_response_with_sources = _create_and_process_rag_prompt(retrieved_documents[0], request.message, self.llm)
        self.send_response(WiseAgentMessage(llm_response_with_sources, self.name), request.sender)
        return True

    def process_response(self, response: WiseAgentMessage):
        '''Do nothing'''
        return True

    def get_recipient_agent_name(self, message):
        '''Return the name of the agent to send the message to.'''
        return self.name

    def stop(self):
        '''Do nothing'''
        pass

    @property
    def name(self) -> str:
        """Get the name of the agent."""
        return self._name

class GraphRAGWiseAgent(WiseAgent):
    """
    This agent implementation is used to test a knowledge graph based RAG agent.
    Use Stomp protocol
    """
    yaml_tag = u'!wiseagents.GraphRAGWiseAgent'

    def __init__(self, name: str, description: str, llm: WiseAgentLLM, graph_db: WiseAgentGraphDB,
                 transport: WiseAgentTransport):
        '''Initialize the agent.

        Args:
            name (str): the name of the agent
            description (str): a description of the agent
            llm (WiseAgentLLM): the LLM agent to use for processing requests
            graph_db (WiseAgentGraphDB): the graph database to use for retrieving documents
            transport (WiseAgentTransport): the transport to use for communication'''
        self._name = name
        self._description = description
        self._transport = transport
        self._graph_db = graph_db
        llm_agent = llm
        super().__init__(name=name, description=description, transport=self.transport, llm=llm_agent,
                         graph_db=graph_db)

    def __repr__(self):
        """Return a string representation of the agent."""
        return (f"{self.__class__.__name__}(name={self.name}, description={self.description}, llm={self.llm},"
                f"graph_db={self.graph_db}, transport={self.transport})")

    def process_event(self, event):
        '''Do nothing'''
        return True

    def process_error(self, error):
        '''Log the error and return True.'''
        logging.error(error)
        return True

    def process_request(self, request: WiseAgentMessage):
        '''Process a request message by passing it to the RAG agent and sending the response back to the client.

        Args:
            request (WiseAgentMessage): the request message to process'''
        retrieved_documents = self.graph_db.query_with_embeddings(query=request.message, k=1, retrieval_query=self._get_retrieval_query())
        llm_response_with_sources = _create_and_process_rag_prompt(retrieved_documents, request.message, self.llm)
        self.send_response(WiseAgentMessage(llm_response_with_sources, self.name), request.sender)
        return True

    def process_response(self, response: WiseAgentMessage):
        '''Do nothing'''
        return True

    def get_recipient_agent_name(self, message):
        '''Return the name of the agent to send the message to.'''
        return self.name

    def stop(self):
        '''Do nothing'''
        pass

    @property
    def name(self) -> str:
        """Get the name of the agent."""
        return self._name

    def _get_retrieval_query(self) -> str:
        '''Return the retrieval query to use for retrieving documents from the graph database.'''
        # this is specific to the test
        return """
          WITH node AS landmark, score AS similarity
          CALL  {
            WITH landmark
            MATCH (landmark)--(city)--(province)--(country)
            RETURN country.name AS Country
          }
          RETURN landmark.name + ' is located in ' + Country AS text, similarity as score, {} AS metadata
        """


class CoVeChallengerRAGWiseAgent(WiseAgent):
    """
    This agent implementation is used to challenge the response from a RAG agent using the
    Chain-of-Verification (CoVe) method (https://arxiv.org/pdf/2309.11495) to try to prevent
    hallucinations.
    Uses the Stomp protocol.
    """
    yaml_tag = u'!wiseagents.CoVeChallengerRAGWiseAgent'

    def __init__(self, name: str, description: str, llm: WiseAgentLLM, vector_db: WiseAgentVectorDB,
                 transport: WiseAgentTransport, collection_name: Optional[str] = "wise-agents-collection",
                 k: Optional[int] = 4, num_verification_questions: Optional[int] = 4):
        """
        Initialize the agent.

        Args:
            name (str): the name of the agent
            description (str): a description of the agent
            llm (WiseAgentLLM): the LLM agent to use for processing requests
            vector_db (WiseAgentVectorDB): the vector database to use for retrieving documents
            transport (WiseAgentTransport): the transport to use for communication
            collection_name Optional(str): the name of the collection to use in the vector database
            k Optional(int): the number of documents to retrieve from the vector database
            num_verification_questions Optional(int): the number of verification questions to generate
        """
        self._name = name
        self._description = description
        self._transport = transport
        self._vector_db = vector_db
        self._collection_name = collection_name
        self._k = k
        self._num_verification_questions = num_verification_questions
        llm_agent = llm
        super().__init__(name=name, description=description, transport=self.transport, llm=llm_agent,
                         vector_db=vector_db, collection_name=collection_name)

    def __repr__(self):
        """Return a string representation of the agent."""
        return (f"{self.__class__.__name__}(name={self.name}, description={self.description}, llm={self.llm},"
                f"vector_db={self.vector_db}, collection_name={self.collection_name}, k={self.k},"
                f"num_verification_questions={self._num_verification_questions}, transport={self.transport})")

    def process_event(self, event):
        """Do nothing"""
        return True

    def process_error(self, error):
        """Log the error and return True."""
        logging.error(error)
        return True

    def process_request(self, request: WiseAgentMessage):
        """
        Process a message containing a question and a baseline response to the question
        by challenging the baseline response to generate a revised response to the original question.

        Args:
            request (WiseAgentMessage): the request message to process
        """
        llm_response = self._create_and_process_chain_of_verification_prompts(request.message)
        self.send_response(WiseAgentMessage(llm_response, self.name), request.sender)
        return True

    def process_response(self, response: WiseAgentMessage):
        """Do nothing"""
        return True

    def get_recipient_agent_name(self, message):
        """Return the name of the agent to send the message to."""
        return self.name

    def stop(self):
        """Do nothing"""
        pass

    @property
    def name(self) -> str:
        """Get the name of the agent."""
        return self._name

    @property
    def k(self) -> int:
        """Get the number of documents to retrieve from the vector database."""
        return self._k

    @property
    def num_verification_questions(self) -> int:
        """Get the number of verification questions to generate."""
        return self._num_verification_questions

    def _create_and_process_chain_of_verification_prompts(self, message: str) -> str:
        """
        Create prompts to challenge the baseline response to a question to try to generate a revised response
        to the original question.

        Args:
            message (str): the message containing the question and baseline response
        """

        """Plan verifications"""
        prompt = (f"Given the following question and baseline response, generate a list of {self.num_verification_questions} "
                  f" verification questions that could help determine if there are any mistakes in the baseline response:\n{message}\n"
                  f"Your response should contain only the list of questions, one per line.\n")
        llm_response = self.llm.process_single_prompt(prompt)

        """Execute verifications"""
        verification_questions = llm_response.content.splitlines()
        verification_responses = ""
        for question in verification_questions:
            retrieved_documents = self.vector_db.query([question], self.collection_name, self.k)
            context = "\n".join([document.content for document in retrieved_documents[0]])
            prompt = (f"Answer the question based only on the following context:\n{context}\n"
                      f"Question: {question}\n")
            llm_response = self.llm.process_single_prompt(prompt)
            verification_responses = (verification_responses + "Verification Question: " + question + "\n"
                                      + "Verification Result: " + llm_response.content + "\n")

        """Generate the final revised response"""
        complete_info = message + "\n" + verification_responses
        prompt = (f"Given the following question, baseline response, and a list of verification questions and results,"
                  f" generate a revised response incorporating the verification results:\n{complete_info}\n"
                  f"Your response must contain only the revised response to the question in the JSON format shown below:\n"
                  f"{{'revised': 'Your revised response to the question.'}}\n")

        llm_response = self.llm.process_single_prompt(prompt)
        return llm_response.content


class SequentialCoordinatorWiseAgent(WiseAgent):
    """
    This agent will coordinate the execution of a sequence of agents.
    Use Stomp protocol.
    """
    yaml_tag = u'!wiseagents.SequentialCoordinatorWiseAgent'

    def __init__(self, name: str, description: str, transport: WiseAgentTransport, agents: List[str]):
        '''Initialize the agent.

        Args:
            name (str): the name of the agent
            description (str): a description of the agent
            transport (WiseAgentTransport): the transport to use for communication
            agents (List[str]): the list of agents to coordinate'''
        self._name = name
        self._agents = agents
        self._route_response_to = ""
        super().__init__(name=name, description=description, transport=transport, llm=None)

    def __repr__(self):
        '''Return a string representation of the agent.'''
        return f"{self.__class__.__name__}(name={self.name}, description={self.description}, agents={self.agents})"

    def process_request(self, request):
        '''Process a request message by passing it to the first agent in the sequence.

        Args:
            request (WiseAgentMessage): the request message to process'''
        logging.debug(f"Sequential coordinator received request: {request}")
        self._route_response_to = request.sender
        ctx = WiseAgentRegistry.get_or_create_context(request.context_name)
        ctx.set_agents_sequence(self._agents)
        self.send_request(WiseAgentMessage(message=request.message, sender=self.name, context_name=request.context_name), self._agents[0])

    def process_response(self, response):
        '''Process a response message by passing it to the next agent in the sequence.

        Args:
            response (WiseAgentMessage): the response message to process'''
        ctx = WiseAgentRegistry.get_or_create_context(response.context_name)
        next_agent = ctx.get_next_agent_in_sequence(response.sender)
        if next_agent is None:
            logging.debug(f"Sequential coordinator sending response from " + response.sender + " to " + self._route_response_to)
            self.send_response(WiseAgentMessage(message=response.message, sender=self.name, context_name=response.context_name), self._route_response_to)
        else:
            logging.debug(f"Sequential coordinator sending response from " + response.sender + " to " + next_agent)
            self.send_request(WiseAgentMessage(message=response.message, sender=self.name, context_name=response.context_name), next_agent)
        return True

    def process_event(self, event):
        '''Do nothing'''
        return True

    def process_error(self, error):
        '''Log the error and return True.'''
        logging.error(error)
        return True

    def get_recipient_agent_name(self, message):
        '''Return the name of the agent to send the message to.

        Args:
            message (WiseAgentMessage): the message to process'''
        return self.name

    def stop(self):
        '''Do nothing'''
        pass

    @property
    def name(self) -> str:
        """Get the name of the agent."""
        return self._name

    @property
    def agents(self) -> List[str]:
        """Get the list of agents."""
        return self._agents

    @property
    def response_delivery(self) -> Optional[Callable[[], WiseAgentMessage]]:
        '''Get the function to deliver the response to the client.
        return (Callable[[], WiseAgentMessage]): the function to deliver the response to the client'''
        return self._response_delivery

    def set_response_delivery(self, response_delivery: Callable[[], WiseAgentMessage]):
        '''Set the function to deliver the response to the client.'''
        self._response_delivery = response_delivery


class PhasedCoordinatorWiseAgent(WiseAgent):
    """
    This agent will coordinate the execution of a group of agents in order to determine the response
    to a query. The agents will be executed in phases, where agents within a phase will be executed
    in parallel. After the phases have completed, the coordinator may choose to repeat the phases
    until it is satisfied with the final response or determines it's not possible to answer the query.
    """
    yaml_tag = u'!wiseagents.PhasedCoordinatorWiseAgent'

    def __new__(cls, *args, **kwargs):
        """Create a new instance of the class, setting default values for the instance variables."""
        obj = super().__new__(cls)
        obj._phases = ["Data Collection", "Data Analysis"]
        obj._max_iterations = MAX_ITERATIONS_FOR_COORDINATOR
        obj._confidence_score_threshold = CONFIDENCE_SCORE_THRESHOLD
        obj._system_message = None
        return obj

    def __init__(self, name: str, description: str, transport: WiseAgentTransport, llm: WiseAgentLLM,
                 phases: Optional[List[str]] = None, max_iterations: Optional[int] = MAX_ITERATIONS_FOR_COORDINATOR,
                 confidence_score_threshold: Optional[int] = CONFIDENCE_SCORE_THRESHOLD, system_message: Optional[str] = None):
        """
        Initialize the agent.

        Args:
            name (str): the name of the agent
            description (str): a description of the agent
            transport (WiseAgentTransport): the transport to use for communication
            llm (WiseAgentLLM): the LLM to use for coordinating the collaboration
            phases (Optional[List[str]]): the optional list of phases, defaults to "Data Collection" and "Data Analysis"
            max_iterations (Optional[int]): the maximum number of iterations to run the phases, defaults to 5
            confidence_score_threshold (Optional[int]): the confidence score threshold to determine if the final answer
            is acceptable, defaults to 85
            system_message (Optional[str]): the optional system message to be used by the coordinator when processing
            chat completions using its LLM
        """
        self._name = name
        self._route_response_to = ""
        self._phases = phases if phases is not None else ["Data Collection", "Data Analysis"]
        self._max_iterations = max_iterations
        self._confidence_score_threshold = confidence_score_threshold
        self._system_message = system_message
        super().__init__(name=name, description=description, transport=transport, llm=llm, system_message=system_message)

    def __repr__(self):
        """Return a string representation of the agent."""
        return (f"{self.__class__.__name__}(name={self.name}, description={self.description}, transport={self.transport},"
                f"llm={self.llm}, phases={self.phases},max_iterations={self.max_iterations}, system_message={self.system_message}")

    @property
    def phases(self) -> List[str]:
        """Get the list of phases."""
        return self._phases

    @property
    def max_iterations(self) -> int:
        """Get the maximum number of iterations."""
        return self._max_iterations

    @property
    def confidence_score_threshold(self) -> int:
        """Get the confidence score threshold."""
        return self._confidence_score_threshold

    def process_request(self, request):
        """
        Process a request message by kicking off the collaboration in phases.

        Args:
            request (WiseAgentMessage): the request message to process
        """
        logging.debug(f"Coordinator received request: {request}")
        self._route_response_to = request.sender

        # Generate a chat ID that will be used to collaborate on this query
        chat_id = str(uuid.uuid4())

        ctx = WiseAgentRegistry.get_or_create_context(request.context_name)

        # Determine the agents required to answer the query
        agent_selection_prompt = ("Given the following query and a description of the agents that are available," +
                                  " determine all of the agents that could be required to solve the query." +
                                  " Format the response as a space separated list of agent names and don't include " +
                                  " anything else in the response.\n" +
                                  " Query: " + request.message + "\n" + "Available agents:\n" +
                                  "\n".join(WiseAgentRegistry.get_agent_names_and_descriptions()) + "\n")
        ctx.append_chat_completion(chat_uuid=chat_id, messages={"role": "system", "content": self.system_message or self.llm.system_message})
        ctx.append_chat_completion(chat_uuid=chat_id, messages={"role": "user", "content": agent_selection_prompt})

        logging.debug(f"messages: {ctx.llm_chat_completion[chat_id]}")
        llm_response = self.llm.process_chat_completion(ctx.llm_chat_completion[chat_id], tools=[])
        ctx.append_chat_completion(chat_uuid=chat_id, messages=llm_response.choices[0].message)

        # Assign the agents to phases
        agent_assignment_prompt = ("Assign each of the agents that will be required to solve the query to one of the following phases:\n" +
                                   ", ".join(self.phases) + "\n" +
                                   "Assume that agents within a phase will be executed in parallel." +
                                   " Format the response as a space separated list of agents for each phase, where the first"
                                   " line contains the list of agents for the first phase and second line contains the list of"
                                   " agents for the second phase and so on. Don't include anything else in the response.\n")
        ctx.append_chat_completion(chat_uuid=chat_id, messages={"role": "user", "content": agent_assignment_prompt})
        llm_response = self.llm.process_chat_completion(ctx.llm_chat_completion[chat_id], tools=[])
        ctx.append_chat_completion(chat_uuid=chat_id, messages=llm_response.choices[0].message)     
        phases = [phase.split() for phase in llm_response.choices[0].message.content.splitlines()]
        ctx.set_agent_phase_assignments(chat_id, phases)
        ctx.set_current_phase(chat_id, 0)
        ctx.add_query(chat_id, request.message)

        # Kick off the first phase
        for agent in phases[0]:
            self.send_request(WiseAgentMessage(message=request.message, sender=self.name,
                                               context_name=request.context_name, chat_id=chat_id), agent)

    def process_response(self, response):
        """
        Process a response message. If this message is from the last agent remaining in the current phase, then
        kick off the next phase of collaboration if there are more phases. Otherwise, determine if we should
        return the final answer or if we need to go back to the first phase and repeat with a rephrased query.

        Args:
            response (WiseAgentMessage): the response message to process
        """
        ctx = WiseAgentRegistry.get_or_create_context(response.context_name)
        chat_id = response.chat_id

        if response.message_type != WiseAgentMessageType.ACK:
            raise ValueError(f"Unexpected response message: {response.message}")

        # Remove the agent from the required agents for this phase
        ctx.remove_required_agent_for_current_phase(chat_id, response.sender)

        # If there are no more agents remaining in this phase, move on to the next phase,
        # return the final answer, or iterate
        if len(ctx.get_required_agents_for_current_phase(chat_id)) == 0:
            next_phase = ctx.get_next_phase(chat_id)
            if next_phase is None:
                # Determine the final answer
                final_answer_prompt = ("What is the final answer for the original query? Provide the answer followed" +
                                       " by a confidence score from 0 to 100 to indicate how certain you are of the" +
                                       " answer. Format the response with just the answer first followed by just" +
                                       " the confidence score on the next line. For example:\n" +
                                       " Your answer goes here.\n"
                                       " 85\n")
                ctx.append_chat_completion(chat_uuid=chat_id,
                                           messages={"role": "user", "content": final_answer_prompt})
                llm_response = self.llm.process_chat_completion(ctx.llm_chat_completion[chat_id], tools=[])
                final_answer_and_score = llm_response.choices[0].message.content.splitlines()
                final_answer = "\n".join(final_answer_and_score[:-1])
                if final_answer_and_score[-1].strip().isnumeric():
                    score = int(final_answer_and_score[-1])
                else:
                    # A score could not be determined
                    score = 0

                # Determine if we should return the final answer or iterate
                if score >= self.confidence_score_threshold:
                    self.send_response(WiseAgentMessage(message=final_answer, sender=self.name,
                                                        context_name=response.context_name, chat_id=chat_id), self._route_response_to)
                elif len(ctx.get_queries(chat_id)) == self.max_iterations:
                    self.send_response(WiseAgentMessage(message=CANNOT_ANSWER, message_type=WiseAgentMessageType.CANNOT_ANSWER,
                                                        sender=self.name, context_name=response.context_name, chat_id=chat_id),
                                       self._route_response_to)
                else:
                    # Rephrase the query and iterate
                    if len(ctx.get_queries(chat_id)) < self.max_iterations:
                        rephrase_query_prompt = ("The final answer was not considered good enough to respond to the original query.\n" +
                                                 " The original query was: " + ctx.get_queries(chat_id)[0] + "\n" +
                                                 " Your task is to analyze the original query for its intent along with the conversation" +
                                                 " history and final answer to rephrase the original query to yield a better final answer." +
                                                 " The response should contain only the rephrased query."
                                                 " Don't include anything else in the response.\n")
                        ctx.append_chat_completion(chat_uuid=chat_id,
                                                   messages={"role": "user", "content": rephrase_query_prompt})
                        # Note that llm_chat_completion[chat_id] is being used here so we have the full history
                        llm_response = self.llm.process_chat_completion(ctx.llm_chat_completion[chat_id], tools=[])
                        rephrased_query = llm_response.choices[0].message.content
                        ctx.append_chat_completion(chat_uuid=chat_id, messages=llm_response.choices[0].message)
                        ctx.set_current_phase(chat_id, 0)
                        ctx.add_query(chat_id, rephrased_query)
                        for agent in ctx.get_required_agents_for_current_phase(chat_id):
                            self.send_request(WiseAgentMessage(message=rephrased_query, sender=self.name,
                                                               context_name=response.context_name, chat_id=chat_id),
                                              agent)
            else:
                # Kick off the next phase
                for agent in next_phase:
                    self.send_request(WiseAgentMessage(message=ctx.get_current_query(chat_id), sender=self.name,
                                                       context_name=response.context_name, chat_id=chat_id), agent)
        return True

    def process_event(self, event):
        """Do nothing"""
        return True

    def process_error(self, error):
        """Log the error and return True."""
        logging.error(error)
        return True

    def get_recipient_agent_name(self, message):
        """
        Return the name of the agent to send the message to.

        Args:
            message (WiseAgentMessage): the message to process
        """
        return self.name

    def stop(self):
        """Do nothing"""
        pass

    @property
    def name(self) -> str:
        """Get the name of the agent."""
        return self._name

    @property
    def response_delivery(self) -> Optional[Callable[[], WiseAgentMessage]]:
        """
        Get the function to deliver the response to the client.
        Returns:
            (Callable[[], WiseAgentMessage]): the function to deliver the response to the client
        """
        return self._response_delivery

    def set_response_delivery(self, response_delivery: Callable[[], WiseAgentMessage]):
        """
        Set the function to deliver the response to the client.
        Args:
            response_delivery (Callable[[], WiseAgentMessage]): the function to deliver the response to the
        """
        self._response_delivery = response_delivery


class CollaboratorWiseAgent(WiseAgent):
    """
    This agent implementation is meant to be used in conjunction with a CoordinatorWiseAgent.
    A collaborator agent will receive a request from a coordinator agent and will process the
    request, adding its response to the shared context. The collaborator agent will then send
    the coordinator agent a message to let the coordinator know that it has finished executing
    its work.
    """
    yaml_tag = u'!wiseagents.CollaboratorWiseAgent'

    def __new__(cls, *args, **kwargs):
        """Create a new instance of the class, setting default values for the instance variables."""
        obj = super().__new__(cls)
        obj._system_message = None
        return obj

    def __init__(self, name: str, description: str, llm: WiseAgentLLM, transport: WiseAgentTransport,
                 system_message: Optional[str] = None):
        """
        Initialize the agent.

        Args:
            name (str): the name of the agent
            description (str): a description of the agent
            llm (WiseAgentLLM): the LLM agent to use for processing requests
            transport (WiseAgentTransport): the transport to use for communication
            system_message (Optional[str]): the optional system message to be used by the collaborator when processing
            chat completions using its LLM
        """
        self._name = name
        self._description = description
        self._transport = transport
        self._llm = llm
        self._system_message = system_message
        super().__init__(name=name, description=description, transport=self.transport, llm=llm, system_message=system_message)

    def __repr__(self):
        """Return a string representation of the agent."""
        return (f"{self.__class__.__name__}(name={self.name}, description={self.description}, llm={self.llm},"
                f"transport={self.transport}, system_message={self.system_message})")

    def process_event(self, event):
        """Do nothing"""
        return True

    def process_error(self, error):
        """Log the error and return True."""
        logging.error(error)
        return True

    def process_request(self, request: WiseAgentMessage):
        """
        Process a request message by passing it to the LLM and then send a response back to the sender
        to let them know the request has been processed.

        Args:
            request (WiseAgentMessage): the request message to process
        """
        ctx = WiseAgentRegistry.get_or_create_context(request.context_name)
        chat_id = request.chat_id
        if chat_id is not None:
            # Get the chat messages so far
            messages = ctx.llm_chat_completion[chat_id]
        else:
            messages = []

        messages.append({"role": "system", "content": self.system_message or self.llm.system_message})
        messages.append({"role": "user", "content": request.message})
        llm_response = self.llm.process_chat_completion(messages, [])

        # Add this agent's response to the shared context
        ctx.append_chat_completion(chat_uuid=chat_id, messages=llm_response.choices[0].message)

        # Let the sender know that this agent has finished processing the request
        self.send_response(
            WiseAgentMessage(message="", message_type=WiseAgentMessageType.ACK, sender=self.name, context_name=request.context_name,
                             chat_id=request.chat_id), request.sender)
        return True

    def process_response(self, response: WiseAgentMessage):
        """Do nothing"""
        return True

    def get_recipient_agent_name(self, message):
        """Return the name of the agent to send the message to.

        Args:
            message (WiseAgentMessage): the message to process
        """
        return self.name

    def stop(self):
        pass

    @property
    def name(self) -> str:
        """Get the name of the agent."""
        return self._name


def _create_and_process_rag_prompt(retrieved_documents: List[Document], question: str, llm: WiseAgentLLM) -> str:
    '''Create a RAG prompt and process it with the LLM agent.

    Args:
        retrieved_documents (List[Document]): the list of retrieved documents
        question (str): the question to ask
        llm (WiseAgentLLM): the LLM agent to use for processing the prompt'''
    context = "\n".join([document.content for document in retrieved_documents])
    prompt = (f"Answer the question based only on the following context:\n{context}\n"
              f"Question: {question}\n")
    llm_response = llm.process_single_prompt(prompt)

    source_documents = ""
    for document in retrieved_documents:
        source_documents += f"Source Document:\n    Content: {document.content}\n    Metadata: {json.dumps(document.metadata)}\n\n"
    llm_response_with_sources = f"{llm_response.content}\n\nSource Documents:\n{source_documents}"
    return llm_response_with_sources

