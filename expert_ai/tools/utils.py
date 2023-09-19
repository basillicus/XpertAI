import pandas as pd
import numpy as np
import os
import re
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from langchain.document_loaders import TextLoader
import xgboost as xgb
import shap
from lime.lime_tabular import LimeTabularExplainer
from scipy import stats
import shutil
import openai
#from langchain.llms import OpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
embedding = OpenAIEmbeddings()

def _split_data(df_init,label,split=0.2):
    ## for test dataset not all 
    df = df_init #pd.read_csv(data_path,header=0)
    df_y = df[label] 
    df_x = df.drop(label,axis = 1)
  
    x_train, x_val, y_train, y_val = train_test_split(df_x, df_y, test_size=split, 
                                                      random_state=42)

    return x_train, x_val, y_train, y_val

def _plots(results,eval_type,savedir):
    x_axis = np.arange(len(results['validation_0'][eval_type]))
    fig, ax = plt.subplots()
    ax.plot(x_axis, results['validation_0'][eval_type], label='Train')
    ax.plot(x_axis, results['validation_1'][eval_type], label='Test')
    ax.legend()
    plt.ylabel(f'{eval_type.upper()}')
    plt.xlabel('Num iterations')
    plt.title(f'XGBoost model evaluation: {eval_type.upper()}')
    plt.show()
    fig.savefig(f'{savedir}/xgbmodel_{eval_type}.png')

def train_xgbclassifier(df_init,label,split=0.2,
                        early_stopping_rounds=5):
    savedir = './data'

    x_train, x_val, y_train, y_val = _split_data(df_init,
                                                            label=label,
                                                            split=split)
    
    ## initialize model
    eval_metric=["auc", "error"]
    xgb_model = xgb.XGBClassifier(objective="binary:logistic", random_state=42,
    eval_metric=eval_metric, early_stopping_rounds=early_stopping_rounds, 
    n_estimators=50)

    xgb_model.fit(x_train, y_train, eval_set=[(x_train, y_train),(x_val, y_val)],
                  verbose=False)
    
    results = xgb_model.evals_result()
    

    ## plot evaluation results
    for metric in eval_metric: 
        _plots(results,metric,savedir)
    
    ## save data
    xgb_model.save_model(f'{savedir}/xgbmodel.json')
    
    np.save(f'{savedir}/xgb_results.npy',results)

def train_xgbregressor(df_init,label,split=0.2, early_stopping_rounds=5):

    savedir = './data'

    x_train, x_val, y_train, y_val = _split_data(df_init,
                                                            label=label,
                                                            split=split)
    
    ## initialize model
    eval_metric=["rmse"]
    xgb_model = xgb.XGBRegressor(objective="reg:squarederror", random_state=42,
                             early_stopping_rounds=early_stopping_rounds)

    xgb_model.fit(x_train, y_train, 
                  eval_set=[(x_train, y_train),(x_val, y_val)],verbose=False)
    
    results = xgb_model.evals_result()
    

    ## plot evaluation results
    for metric in eval_metric: 
        _plots(results,metric,savedir)
    
    ## save data
    xgb_model.save_model(f'{savedir}/xgbmodel.json')
    np.save(f'{savedir}/xgb_results.npy',results)


def get_response(prompt):
    messages = [{"role": "user", "content": prompt}]
    response = openai.ChatCompletion.create(model="gpt-4",
                                            messages=messages,temperature=0,)

    return response.choices[0].message["content"]

def explain_shap(df_init,model_path,label,top_k,classifier=False):
    savedir = './data'

    df = df_init #pd.read_csv(data_path,header=0,delim_whitespace=True)
    ## use all data for the shap analysis
    df_x = df.drop(label,axis = 1)

    feat_labs = list(df_x)
    model = xgb.Booster()
    model.load_model(model_path)

    results = np.load(f'{savedir}/xgb_results.npy',allow_pickle=True).item()
    
    ## retreive metrics from the last iteration
    #order: [train_auc,train_error,test_auc,test_err
    if classifier:
        met_exp = ["Train AUC","Train Error","Test AUC","Test Error"]
        metrics = [results['validation_0']['auc'][-1],
                results['validation_0']['error'][-1],
                results['validation_1']['auc'][-1],
                results['validation_1']['error'][-1]]
    else: 
        met_exp = ["Train RMSE","Test RMSE"]
        metrics = [results['validation_0']['rmse'][-1],
                results['validation_1']['rmse'][-1]]
        

    
    ## SHAP analysis
    explainer = shap.Explainer(model,df_x)
    shap_values = explainer(df_x)

    fig, ax = plt.subplots(figsize=(4,4))
    shap.summary_plot(shap_values, df_x, plot_type="bar",max_display=top_k,show=False)
    plt.title('SHAP analysis')
    plt.xlabel('Average impact')
    fig.savefig(f'{savedir}/shap_bar.png',bbox_inches='tight', dpi=300)

    #compute average impact
    avg_impacts = shap_values.abs.mean(0).values
    top_fts_args = np.flip(np.argsort(avg_impacts))

    pearsons = {}
    avg_im = {}
    for i in top_fts_args[:top_k]:
        shap_y = shap_values[:,i].values
        data_x = shap_values[:,i].data
        ft = feat_labs[i]
        pearsons[ft] = np.corrcoef(data_x, shap_y)[0][1]
        avg_im[ft] = avg_impacts[i]

    summary = f'The model can be evaluated with the following metrics.'

    for i,val in enumerate(metrics):
        summary+= f"Model's {met_exp[i]} is {val}. "

    summary = f'The model can be explained with the following SHAP analysis.'
    for k, v in pearsons.items():
        summary+= f"Feature {k} has a correlation coefficient of  {v} with its SHAP values. \nThe average impact of {k} is {avg_im[k]}.\n "

    shap_summary = summary
    ## save SHAP summary
    #f = open(f'{savedir}/shap_summary.txt',"w+")
    #f.write(shap_summary)
    #f.close()
    
    #np.save(f'{savedir}/top_shap_fts.npy',list(pearsons.keys())) 

    #vector_db(lit_file=f'{savedir}/shap_summary.txt',
    #          clean=True)
    
    return list(pearsons.keys()), shap_summary

def _load_split_docs(filename):
    r_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=200,
        length_function=len
    )
    if filename.endswith('.pdf'):
        docs = PyPDFLoader(f'{filename}').load()
    elif filename.endswith('.txt'):
        docs = TextLoader(f'{filename}').load()

    docs_split = r_splitter.split_documents(docs)

    return docs_split

def _create_vecdb(docs_split,persist_directory):

    vectordb = Chroma.from_documents(
            documents=docs_split,
            embedding=embedding,
            persist_directory=persist_directory)
        
    vectordb.persist()

def _update_vecdb(docs_split,persist_directory):
    vectordb = Chroma(persist_directory=persist_directory, 
                                    embedding_function=embedding)
                
    vectordb.add_documents(documents=docs_split,
            embedding=embedding,
            persist_directory=persist_directory)
    
    vectordb.persist() 

def vector_db(lit_directory=None, persist_directory=None, 
              lit_file=None,clean=False):
    
    if persist_directory is None:
        persist_directory="./data/chroma/"
    
    ## Delete and create persist directory
    if lit_file is not None:
       text_split = _load_split_docs(f'{lit_file}')
    
       if clean:
           if os.path.exists(persist_directory):
            shutil.rmtree(persist_directory)
            
            os.mkdir(persist_directory)
            _create_vecdb(text_split ,persist_directory)
            

       else:
           _update_vecdb(text_split,persist_directory)

    # Split & embed from lit files
    if  lit_directory is not None:
        
        if clean:
            shutil.rmtree(persist_directory)

        for doc in os.listdir(lit_directory):
            docs_split = _load_split_docs(f'{lit_directory}/{doc}')

            if os.path.exists(persist_directory):
                _update_vecdb(docs_split,persist_directory)
                
        
            else: 
                os.mkdir(persist_directory)
                _create_vecdb(docs_split, persist_directory)


def explain_lime(df_init,model_path,model_type,top_k,label):
   weights = []
   num_samples = 200
   savedir = './data'
   #df = pd.read_csv(data_path,header=0)
   ## use all data for the shap analysis
   df_x = df_init.drop(label,axis = 1)
   
   if model_type=='classifier': 
       class_names=[0,1]
       mode = "classification" 
   else: 
       class_names=[f'{label}']
       mode = "regression"

   explainer = LimeTabularExplainer(df_x.values, 
                                    feature_names=list(df_x.columns), 
                                    class_names=class_names,
                                    mode=mode)
   
   df_sample = df_x.sample(num_samples)
   num_fts = len(list(df_x.columns))

   for i in range(len(df_sample)):
        if model_type=='classifier':
            model = xgb.XGBClassifier()
            model.load_model(model_path)
            exp = explainer.explain_instance(df_sample.iloc[i], model.predict_proba, 
                                             num_features=num_fts, top_labels=True)
        else: 
            model = xgb.XGBRegressor()
            model.load_model(model_path)
            exp = explainer.explain_instance(df_sample.iloc[i], model.predict, 
                                             num_features=num_fts, top_labels=True)
        exp_map = exp.as_map()
        cls = list(exp_map.keys())[0]
        #sort weights otherwise they are printed from highest to lowest w
        exp_map[cls].sort(key=lambda x: x[0])
        ws = np.array(exp_map[cls])[:,-1]
        zscore = stats.zscore(ws)
        weights.append(zscore)
        
   global_w = np.sum(np.vstack(weights),axis=0)

   ## get top k features from LIME values
   top_fts = np.array(df_x.columns)[abs(global_w).argsort()[-top_k:][::-1]]
   lime = global_w[abs(global_w).argsort()[-top_k:][::-1]]
   y_pos = np.arange(top_k)

   ## plot LIME analysis 
   fig, ax = plt.subplots()
   ax.barh(y_pos, lime)
   ax.set_yticks(y_pos, labels=top_fts )
   ax.invert_yaxis()  # labels read top-to-bottom
   ax.set_xlabel('Z-score lime values')
   ax.set_ylabel('Features')
   ax.set_title('LIME analysis')
   fig.savefig(f'{savedir}/lime_bar.png',
               bbox_inches='tight', dpi=300)
   
   ## write summary of LIME analysis
   summary = f'To explain the model behavior, LIME explanations were generated. \
    \nPlease note these are global observations based on {num_samples} data points.'
   
   for ft, l in zip(top_fts,lime):
        summary+= f"Feature {ft} has an average\n \
             z-score of {l} with towards the prediction.\n"
        
   '''prompt = f"Summarize and write an brief of the model behavior \
    from the following: {summary}"
   
   lime_summary = get_response(prompt) 
   np.save(f'{savedir}/top_{top_k}_lime_fts.npy',top_fts)
  '''
   return top_fts, summary
  
