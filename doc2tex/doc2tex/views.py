import os
import re
import uuid
import shutil
import string
import git
import subprocess
import sys  

import locale
def getpreferredencoding(do_setlocale = True):
   return "utf-8"
locale.getpreferredencoding = getpreferredencoding
  

from pyramid.view import view_config  
from pyramid.response import Response
import pyramid.httpexceptions as exc

import logging
log = logging.getLogger(__name__)

from langsci.convertertools import  convert
from langsci.sanity import  SanityDir
from langsci.bibtools import  normalize
#from .lib import  sanityoverleaf
from langsci.bibtools import Record

@view_config(route_name='doc2tex', renderer='templates/mytemplate.pt')
def doc2tex(request):
  return {'project': 'doc2tex'}

  
@view_config(route_name='doc2bib', renderer='templates/doc2bib.pt')
def doc2bib(request): 
        biboutput = ''
        try:
                bibinput = request.POST['bibinput'].strip()
                biboutput = '\n\n'.join([Record(l).bibstring for l in bibinput.split('\n')])
                #biboutput = '\n'.join([str(len(l)) for l in bibinput.split('\n')])
        except KeyError:
                #bibinput = "Paste your bibliography here" 
                bibinput = """Bloomfield, Leonard. 1925. On the sound-system of central Algonquian. Language 1(4). 130-156.

Lahiri, Aditi (ed.). 2000. Analogy, leveling, markedness: Principles of change in phonology and morphology (Trends in Linguistics 127). Berlin: Mouton de Gruyter.
""" 
        return {'project': 'doc2bib',
        'bibinput': bibinput,
        'biboutput': biboutput
                                }
    
    
@view_config(route_name='normalizebib', renderer='templates/normalizebib.pt')
def normalizebib(request): 
        biboutput = ''
        try:
                bibinput = request.POST['bibinput'].strip()
                biboutput = normalize(bibinput)
        except KeyError:
                bibinput = """
%This is a comment

@article{Jones1999,
  author = {Jane Jones et al},
  year = {1999},
  title = {Exploring unknown movements of NP},
  journal = {Annals of Improbable research}
}

@BOOK{Smith2000,
  author = {John Smith},
  year = {2000},
  title = {A Grammar of the Turkish Language},
  publisher = {Oxford University Press}
}
"""
        #biboutput = bibinput
        return {'project': 'normalizebib',
        'bibinput': bibinput,
        'biboutput': biboutput
                                }
    
@view_config(route_name='sanitycheck', renderer='templates/sanitycheck.pt')
def sanitycheck(request):   
    fn = request.POST['texbibzip'].filename 
    input_file = request.POST['texbibzip'].file
    filename = _upload(fn, input_file,('tex', 'bib')) 
    filetype = filename.split('.')[-1]
    d = os.path.dirname(os.path.realpath(filename))
    basename = filename.split('/')[-1]
    path = filename.split('/')[:-1]
    newpath = '/'.join(path)+'/local-'+basename
    os.rename(filename, newpath) 
    lspdir = SanityDir(d,ignorecodes=[])    
    lspdir.check()  
    #shutil.rmtree(d)
    return {'project': 'doc2tex',
            'files':lspdir.texterrors,
            'imgs':[]}
  
@view_config(route_name='githubsanity', renderer='templates/sanitycheck.pt')
def githubsanity(request):   
    def cloneorpull(url):
        """
        Make a git repository available locally. 
        
        The repo is cloned if not already available locally, otherwise, it is pull'ed.
        
        args:
        url (str): the url string of the repository. It can be either the html URL or the git url
        
        returns
        str: the file path to the local repo
        
        """
        m = re.search('langsci/([0-9]{2,}a?)',url)
        try:            
            githubID = m.group(1)
        except AttributeError:
            raise GitHubError(url)
        print("GitHub ID found:", githubID)
        giturl = "https://github.com/langsci/%s.git"%githubID
        gitdir = os.path.join(os.getcwd(),githubID)
        print("git repo is ", giturl)
        try:
            git.Repo.clone_from(giturl, gitdir)
            print("cloned")
        except git.exc.GitCommandError:
            print("repo already in file system. Pulling")
            cwd = os.getcwd()
            print(gitdir)
            os.chdir(gitdir)
            subprocess.call(["git","pull"]) 
            os.chdir(cwd)
            print("pulled")
        return gitdir 

    githuburl = request.GET['githuburl']
    try:
        d = cloneorpull(githuburl)
    except FileNotFoundError: 
        raise GitHubError(githuburl)
    texdir = SanityDir(os.path.join(d,"."),ignorecodes=[])
    texdir.check()
    imgdir = SanityDir(os.path.join(d,"."),ignorecodes=[])
    imgdir.check()
    #shutil.rmtree(d)
    return {'project': 'doc2tex',
            'files':texdir.texterrors,
            'imgs':imgdir.imgerrors}
  
    
def _upload(filename,f,accept):
    inputfn = ''.join([c for c in filename if c in string.ascii_letters or c in string.digits or c =='.'])
    input_file = f
    filetype = inputfn.split('.')[-1]
    if filetype not in accept:
        raise WrongFileFormatError(filetype,accept)
    tmpdir = '%s'%uuid.uuid4() 
    os.mkdir(os.path.join('/tmp',tmpdir))
    #tmpfile = '%s.%s' % (uuid.uuid4(),filetype)
    file_path = os.path.join('/tmp',tmpdir,inputfn)
     
    # We first write to a temporary file to prevent incomplete files from
    # being used.
    temp_file_path = file_path + '~'
    output_file = open(temp_file_path, 'wb')
    # Finally write the data to a temporary file
    input_file.seek(0)
    while True:
        data = input_file.read(2<<16)
        if not data:
            break
        output_file.write(data)          
    output_file.close()
    # Now that we know the file has been fully saved to disk move it into place.
    os.rename(temp_file_path, file_path) 
    #log.error('filepath: %s'% file_path)
    return file_path
      

@view_config(route_name='result', renderer='templates/result.pt')
def result(request):  
    fn = request.POST['docfile'].filename
    input_file = request.POST['docfile'].file
    filename = _upload(fn, input_file,('doc', 'docx', 'odt'))
    #convert file to tex
    try:
        texdocument = convert(filename)
        texdocument.ziptex()    
    except UnicodeEncodeError:
        raise Writer2LatexError()
    #except IOError:
        #raise Writer2LatexError 
    #os.remove(filename)
    texttpl = (('raw',texdocument.text),
               ('mod',texdocument.modtext),
               ('chapter',texdocument.papertext),
               ('preamble',"\n\n".join(["%Copy this to localcommands.tex",
                                        texdocument.packages,
                                        texdocument.environments,
                                        texdocument.commands,
                                        texdocument.counters,
                                        ])
              ))
    return {'project': 'doc2tex',
            'filename': fn,
            'texttpl': texttpl, 
            'zipurl': "http://www.glottotopia.org/wlport/%s.zip"%texdocument.zipfn}
            

class FileFormatFailure(Exception):
    pass

@view_config(context=FileFormatFailure, renderer='templates/error.pt')
def failed_conversion(exc, request):
    # If the view has two formal arguments, the first is the context.
    # The context is always available as ``request.context`` too.
    filetype = exc.args[0] if exc.args else ""
    response =  Response('Failed conversion: file of type %s could not be converted. A common cause is a table of contents or other automated index. Remove this from your file, save, and try again.' %filetype)
    response.status_int = 500
    return response
    
class WrongFileFormatError(Exception):
    pass

@view_config(context=WrongFileFormatError, renderer='templates/error.pt')
def wrongfileformat(exc, request):
    # If the view has two formal arguments, the first is the context.
    # The context is always available as ``request.context`` too.
    filetype,accept = exc.args[0] if exc.args else "",""
    msg =  'Files of type %s are not accepted. The only file types accepted are %s' % (filetype, ", ".join(accept))
    return {'project': 'doc2tex',
            'msg': msg }
            
            
    
class GitHubError(Exception):
    pass

@view_config(context=GitHubError, renderer='templates/error.pt')
def wronggithubID(url, request): 
    #url = exc.args[0] if exc.args else "",""
    msg =  'Not a valid LangSci ID on GitHub: %s' % url
    return {'project': 'doc2tex',
            'msg': msg }
                        
             
class Writer2LatexError(Exception):
    pass

@view_config(context=Writer2LatexError, renderer='templates/error.pt')
def w2lerror(exc, request):
    # If the view has two formal arguments, the first is the context.
    # The context is always available as ``request.context`` too.
    filetype = exc.args[0] if exc.args else ""
    msg =  """The file could not be converted. Common causes are:
                 1. file format. *odt is best, *doc is also possible, *docx is the most problematic format 
                 2. Faulty Unicode
                 3. an automatic table of contents
                 4. many graphics 
                 5. complicated tables. Remove problematic elements from your file, save in another format and retry.
    """ 
    return {'project': 'doc2tex',
            'msg': msg }
            
