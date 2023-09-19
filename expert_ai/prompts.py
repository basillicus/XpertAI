GENERAL_TEMPLATE ="""You will assume the the role of a scientific assistant. 
The solution draft follows the format "Thought, Action, Action Input, Observation", where the 'Thought' statements describe a reasoning sequence.
Your task is to Process the {query} as best you can based on the solution draft.
The answer should have an educative and assistant-like tone, be accurate.
"""

FORMAT_INSTRUCTIONS = """
You can only respond with a single complete
"Thought, Action, Action Input" format
OR a single "Final Answer" format.

Complete format:

Thought: (reflect on your progress and decide what to do next)
Action: (the action name should be one of the tools)
Action Input: (the input string to the action)

OR

Final Answer: (the final answer to the original input question)
"""

EXPLAIN_TEMPLATE= """Please explain how each important features identified by 
    SHAP analysis affects the observation {observation}. 
    You can follow the provided draft to answer:

    1. List of important features are most impactful SHAP features are: {ft_list}.
    
    2. Find the relationship of the <features> with the {obsertvation}
    eg:
    ``The relationship of <feature 1> with the {obsertvation} is ...
      The relationship of <feature 2> with the {obsertvation} is ...
      The relationship of <feature 3> with the {obsertvation} is ... ``
    
    3. Explain how the <feature> affect the {obsertvation}
    eg:
    ``<feature 1> affect the {obsertvation} by ...
      <feature 2> affect the {obsertvation} by ...
      <feature 3> affect the {obsertvation} by ... ``
    
    4. Explain how the {observation} be altered by changing the <features>
    eg:
    ``The {obsertvation} will change postively/negatively when <feature 1> changes because...
      The {obsertvation} will change postively/negatively when <feature 2> changes because...
      The {obsertvation} will change postively/negatively when <feature 3> changes because...
    
    5. Assume the role of a scientific assistant and summarize answers in steps 1-4. 
    Explain on how the {obsertvation}  can be altered with respect to all the features: {ft_list}. Give scientific reasoning for these answers.

    """
