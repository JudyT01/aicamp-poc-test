# Set up and run this Streamlit App
import pysqlite3
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import os
import streamlit as st
from crewai import Crew, Process, Agent, Task
from crewai_tools import ScrapeWebsiteTool, PDFSearchTool, FileReadTool
from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI
from typing import Any, Dict
from dotenv import load_dotenv
from openai import OpenAI
from helper_functions.utility import check_password


# Set your OpenAI API key
if load_dotenv('.env'):
   # for local development
   OPENAI_KEY = os.getenv('OPENAI_API_KEY')
else:
   OPENAI_KEY = st.secrets['OPENAI_API_KEY']

# Pass the API Key to the OpenAI Client
client = OpenAI(api_key=OPENAI_KEY)

# Initialize the OpenAI model for use with agents
openai = ChatOpenAI(model="gpt-4o-mini", temperature=0)

class CustomHandler(BaseCallbackHandler):
    """A custom handler for logging interactions within the process chain."""
    
    def __init__(self, agent_name: str) -> None:
        super().__init__()
        self.agent_name = agent_name

    def on_chain_start(self, serialized: Dict[str, Any], outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Log the start of a chain with user input."""
        st.session_state.messages.append({"role": "assistant", "content": outputs['input']})
        st.chat_message("assistant").write(outputs['input'])
        
    def on_agent_action(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any) -> None:
        """""Log the action taken by an agent during a chain run."""
        st.session_state.messages.append({"role": "assistant", "content": inputs['input']})
        st.chat_message("assistant").write(inputs['input'])
        
    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Log the end of a chain with the output generated by an agent."""
        st.session_state.messages.append({"role": self.agent_name, "content": outputs['output']})
        st.chat_message(self.agent_name).write(outputs['output'])

#Tools
cpf_medisave_urls = ('https://www.cpf.gov.sg/member/healthcare-financing/using-your-medisave-savings', 
            'https://www.cpf.gov.sg/member/healthcare-financing/using-your-medisave-savings/using-medisave-for-outpatient-treatments',
            'https://www.cpf.gov.sg/member/healthcare-financing/using-your-medisave-savings/using-medisave-for-hospitalisation',
            'https://www.cpf.gov.sg/member/healthcare-financing/using-your-medisave-savings/applying-to-use-your-healthcare-plans',
            )
tool_webscrape = ScrapeWebsiteTool(url=cpf_medisave_urls)
pdf_search_tool = PDFSearchTool(pdf='https://www.cpf.gov.sg/content/dam/web/member/healthcare/documents/InformationBookletForTheNewlyInsured.pdf')
file_tool = FileReadTool()

# Define agents with their specific roles and goals
information_retrieval_agent = Agent(
    role='Medishield Information Provider',
    goal='To thoroughly and accurately search and extract text, tables, and images from the given PDF document',
    backstory="""\
                You are good at following instructions.
                You are a professional PDF extraction expert.
                Search thoroughly and ensuring that every piece of the relevant information is accurately extracted 
                and present in a clear, structured format, such as lists or tables, to enhance readability.
                The data you collected MUST ONLY contains information from the PDF document""",
    tools=[pdf_search_tool],
    verbose=True,
    llm=openai,
    callbacks=[CustomHandler("Medishield Information Provider")],
)

researcher = Agent(
    role='Medisave Researcher',
    goal='Perform thorough analysis on Singapore CPF medisave URLs to assist users on their healthcare needs.',
    backstory="""\
                You are good at following instructions.
                You are a Singapore CPF Medisave Researcher.
                You are an expert in navigating and extracting relevant information on Singapore CPF medisave URLs, including its overview, eligibility, benefits,  
                where can you use MediSave and the application process. The data you collected MUST ONLY contains information from Singapore CPF medisave URLs""",
    tools=[tool_webscrape],
    verbose=True,
    llm=openai,
    callbacks=[CustomHandler("Medisave Researcher")],
)

customer_service_agent = Agent(
    role='Customer Service Officer',
    goal='Response to the customer query with the relevant information provided by the researcher agent or the information retrieval agent, ensuring the responses are accurate, helpful, easy to read and understand.',
    backstory="""\
                You are good at following instructions.
                You are a senior customer service officer on healthcare financing. 
                You get relevant information from the researcher agent or information retrieval agent
                to answer queries regarding Singapore CPF Medishield Life and Singapore CPF MediSave, 
                including Medishield coverage and premiums payment, benefits, government subsidies,  
                making a claim, exclusions, additional private insurance and MediSave usage.""",
    tools=[file_tool],
    verbose=True,
    llm=openai,
    callbacks=[CustomHandler("Customer Service Officer")],
)

# Streamlit UI setup

# region <--------- Streamlit App Configuration --------->
st.set_page_config(
    layout="centered",
    page_title="My Streamlit App"
)
# endregion <--------- Streamlit App Configuration --------->

st.title("Dear Citizen, Welcome to your MediShield Life and MediSave's Info Buddy!")

# Check if the password is correct.  
if not check_password():  
    st.stop()



# Initialize the message log in session state if not already present
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "content": "How can I help you navigate your healthcare planning today? Your well-being is our priority!"}]

# Display existing messages
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# Handle user input
if prompt := st.chat_input():
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    # Define tasks for each agent
    task_medishield_information_provider = Task(
        description=f"""
                    Your instructions are as follows:
                    Step 1: Check does '{prompt}' contain keywords: Medishield, benefit, coverage, premium, payment, policy, subsidies,
                    deductible, claim, co-insurance, exclusions, insurance, healthcare, protection, hospital, ward, 
                    outpatient, surgery, treatment,  pro-ration, withdrawal, limit.
                    Step 2: If '{prompt}' NO keywords, PASS THE TASK TO NEXT AGENT AND END YOUR TASK IMMEDIATELY. 
                    Step 3: If '{prompt}' have keywords, GO to PDF document in ({pdf_search_tool}).
                    Step 4: Use the tools to extract every piece of relevant information from the PDF ONLY which are related to '{prompt}'.
                    Step 5: Present the extracted information in a clear, structured format, such as lists or tables, to enhance readability.
                    """,
        agent=information_retrieval_agent,
        expected_output="Present relevant information in a clear, structured format, such as lists or tables for the customer service agent to complete the task.",
    )
    
    task_medisave_researcher = Task(
        description=f"""
                    Your instructions are as follows:
                    Step 1: Analyze all CPF medisave URLs provided in ({cpf_medisave_urls}) to extract relevant information related to '{prompt}'.
                    Step 2: Use the tools to gather relevant information from CPF medisave urls provided in ({cpf_medisave_urls}) ONLY.
                    Step 3: If you are not able to find anything on all CPF medisave URLs provided in ({cpf_medisave_urls}), END YOUR TASK IMMEDIATELY.
                    """,
        agent=researcher,
        expected_output="A structured list of relevant information for the customer service agent to complete the task.",
    )
  
    task_customer_service_agent = Task(
        description=f"""
                    Your instructions are as follows:
                    Use ONLY the FINAL answer given by the information retrieval agent or researcher agent.
                    DO NOT ADD any additional information.
                    DO NOT MAKE UP any information. If you DO NOT have the information or answers, response: 'I'm sorry. I do not have the answer to this enquiry.' 
                    Write a detailed response to the customer with the following:
                    1. Fellow Citizen, thank you for your enquiry.
                    2. Detailed response with the FINAL answer in a clear and concise format.
                    3. If you DO NOT have the information or answers, just say: 'I'm sorry. I do not have the answer to this enquiry.
                    4. Lastly, provide customer a healthcare tip at the end of the conversation.
                    """,
        agent=customer_service_agent,
        expected_output="Write a detailed response to the customer in a clear and concise format with the FINAL answer given by the information retrieval agent or researcher agent ONLY.",
    )
    
    # Set up the crew and process tasks hierarchically
    project_crew = Crew(
        tasks=[task_medishield_information_provider, task_medisave_researcher, task_customer_service_agent],
        agents=[information_retrieval_agent, researcher, customer_service_agent],
        process=Process.hierarchical,
        manager_llm=openai,
        manager_callbacks=[CustomHandler("Crew Manager")]
    )
    final = project_crew.kickoff()

    # Display the final result
    result = f"## Thanks for waiting. Here is the information you requested. \n\n {final}"
    st.session_state.messages.append({"role": "assistant", "content": result})
    st.chat_message("assistant").write(result)


with st.expander("Disclaimer"): 
    st.write("IMPORTANT NOTICE: This web application is a prototype developed for educational purposes only. \
       The information provided here is NOT intended for real-world usage and should not be relied upon for making any decisions, \
       especially those related to financial, legal, or healthcare matters. Furthermore, please be aware that the LLM may generate \
       inaccurate or incorrect information. You assume full responsibility for how you use any generated output. Always consult with \
       qualified professionals for accurate and personalized advice.")
