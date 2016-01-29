"use strict"

var parsedConfig = null;
var ajaxLink = "";
var data = {};
var nodes = [];
var nodesContainer = null;
var frameCount = 0;
var appViewConfig = {};
var domNodeHeight = 100;
var domDemoCaseVMExtraPadding = 40;
var xhrErrorCount = 0;
var intervalExec;

window.onload = function(){
    getAndExecute("gui_config.json", setLinkAndParseHTML);
}

/////////////////////////Configuration functions//////////////////////////////////////////

function setLinkAndParseHTML(text, parserFunction){
    parsedConfig = JSON.parse(text);
    ajaxLink = parsedConfig.ajaxlink+'/getOverviewData';
    getAndExecute('appViewConfig.json', loadViewSpecs);
    getAndExecuteWrapper();
    intervalExec = setInterval(getAndExecuteWrapper, 3000);
}

function loadViewSpecs(text){
    appViewConfig = JSON.parse(text); 
}

function getAndExecute(link, callback){
    var xhr = new XMLHttpRequest();
    xhr.open("GET", link, true);
    xhr.withCredentials = true;
    xhr.onreadystatechange = function(){
        if(xhr.readyState === 4){
            callback(xhr.responseText);
        }
    }
    xhr.send(null);
}

function getAndExecuteWrapper(){
    getAndExecute(ajaxLink, JSONToHTML);
    frameCount++;
}

/////////////////////////DOM functions///////////////////////////////////////////////////

function JSONToHTML(text){
    try{
        data = JSON.parse(text);
    }catch(err){
        data = {};
        xhrErrorCount++;
        if(xhrErrorCount>2){
            clearInterval(intervalExec);
            dropCurtain();
        }
        if(window.console){
            if(window.console.log){
                console.log(err.description);                
            }
            else if(window.console.assert){
                console.assert(err.description);
            }
        }
    }
    nodes = [];
    //nodes.unshift(createDOMElement('div', '<h3>Fuel</h3>', 'eaCEEGUI-raNode eaCEEGUI-raNode-cic ebBgColor_darkBlue_80', 'FuelNode'));
    for(var aNode in data){
        if(aNode.match(/cic\-/i))
            nodes.unshift(createDOMElement('div', '<h3>'+aNode.split('\.domain')[0]+'</h3>', 'eaCEEGUI-raNode-cic ebBgColor_darkBlue_80', aNode));
        else
            nodes.push(createDOMElement('div', '<h3>'+aNode.split('\.domain')[0]+'</h3>', 'eaCEEGUI-raNode', aNode));    
    }
    nodesContainer = document.getElementById('contentHolder');
    nodesContainer.innerHTML = '';
    //objectToDivs(nodesContainer, data);
    
    for(var i=0; i<nodes.length; i++){
        if(!nodes[i].id.match(/cic\-/i)){
            if(data[nodes[i].id]['state']=='up'){
                nodes[i].className += ' ebBgColor_darkBlue_80';
            }else{
                nodes[i].className += ' ebBgColor_grey_60';
            }
            if(data[nodes[i].id]['isEnabled']=='enabled'){
                nodes[i].getElementsByTagName('h3')[0].className += ' ebBgColor_darkBlue_80';
            }else{
                nodes[i].getElementsByTagName('h3')[0].className += ' ebBgColor_grey_80';
            }
        }       
        if('applications' in data[nodes[i].id]){
            var appsContainer = createDOMElement('div', '', 'eaCEEGUI-raNode-raAppsContainer', nodes[i].id+'-appsContainer');
            for(var anApp in data[nodes[i].id]['applications']){
                if(appViewConfig[anApp]['visibility']){
                    var cssClassToAdd = appViewConfig[anApp]['isDemoCase'] ? 'eaCEEGUI-raNode-raApp-innerContainerDemoCase' : 'eaCEEGUI-raNode-raApp-innerContainer';
                    var callDiv = data[nodes[i].id]['applications'][anApp]['calls']!=undefined ? '<div style="font-size:0.8em">Calls : '+data[nodes[i].id]['applications'][anApp]['calls']+'</div>':'';
                    createDOMElementAndAdd(
                        'div', 
                        appsContainer, 
                        '<div class=" '+ cssClassToAdd+'"><div>' + anApp + '</div>'+callDiv+'</div>', 
                        'eaCEEGUI-raNode-raApp', 
                        anApp+'-'+nodes[i].id);
                }
            }           
        nodes[i].appendChild(appsContainer);
        }
        nodesContainer.appendChild(nodes[i]);
        setDemoCases();
    }
    nodesContainer.insertBefore(createDOMElement('div', '<h3>Fuel</h3>', 'ebBgColor_darkGreen_80 eaCEEGUI-raNode-cic', 'FuelNode'), nodesContainer.childNodes[0]);
    setNodeWidth(nodes.length-3, 300);
}

function createDOMElement(elementType, HTMLstring, cssClass, elementId){
    var elementToAdd = document.createElement(elementType);
    elementToAdd.className = cssClass;
    if(typeof elementId != 'undefined'){
        elementToAdd.id = elementId;
    }
    elementToAdd.innerHTML = HTMLstring;
    return elementToAdd;
}

function createDOMElementAndAdd(elementType, parent, HTMLstring, cssClass, elementId){
    var elementToAdd = createDOMElement(elementType, HTMLstring, cssClass, elementId);
    parent.appendChild(elementToAdd);
}

function setDemoCases(){
    //padding fix for the VMs/apps' demo cases. Ugly solution. 
    var fixPadding = function(apps){
        for(var i=0; i<apps.length; i++){       
            var padding = domNodeHeight/(2*apps[i].parentNode.parentNode.childNodes.length);
            apps[i].style.paddingTop = padding +'px';
            apps[i].style.paddingBottom = padding+'px';
        }
    }
    var apps = document.getElementsByClassName('eaCEEGUI-raNode-raApp-innerContainer');
    fixPadding(apps);
    apps = document.getElementsByClassName('eaCEEGUI-raNode-raApp-innerContainerDemoCase');
    fixPadding(apps);
}

function setNodeWidth(nodesNum, offset){
    var newWidth = (document.documentElement.clientWidth-offset)/nodesNum;
    var nodes  = document.getElementsByClassName('eaCEEGUI-raNode');
    var loopAndSet = function(elements, nWidth){
        for(var i=0;i<elements.length; i++){
            elements[i].style.width = nWidth + 'px';
        }
    }
    loopAndSet(document.getElementsByClassName('eaCEEGUI-raNode'), newWidth);
    loopAndSet(document.getElementsByClassName('eaCEEGUI-raNode-raAppsContainer'), newWidth);
    loopAndSet(document.getElementsByClassName('eaCEEGUI-raNode-raApp-innerContainerDemoCase'), newWidth-20);
    loopAndSet(document.getElementsByClassName('eaCEEGUI-raNode-raApp-innerContainer'), newWidth-20);
}

function dropCurtain(){
    var curtain = createDOMElement('div', '', 'eaCEEGUI-rCurtain', 'errorCurtain');
    document.body.insertBefore(curtain, document.body.childNodes[0]);
}