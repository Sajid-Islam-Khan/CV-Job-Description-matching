# CV-Job-Description-matching

Environment setup & dependencies for the project:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass #access to venv
rm -r venv                                                 #remove first if venv exists
python -m venv venv                                        #create your venv
.\venv\Scripts\Activate                                    #activate venv

pip install flask
pip install pdfplumber
pip install spacy
python -m spacy download en_core_web_sm
pip install pandas
pip install openpyxl
pip list
pip install gensim
pip install nltk
pip install numpy
pip install requests
pip install PyPDF2
pip install ploty

python app.py                                              #run project
