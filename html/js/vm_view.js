"use strict"

var parsedConfig = null;
var ajaxLink = "";
var data = {};
var nodes = [];
var nodesContainer = null;
var frameCount = 0;
var appViewConfig = {};
var domNodeHeight = 200;
var domDemoCaseVMExtraPadding = 40;
var xhrErrorCount = 0;
var loadBarRefNum = 5;
var intervalExec;
var latestEventString = "";

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
    document.getElementById('scale_out').onclick = scaleOut;
    document.getElementById('scale_in').onclick = scaleIn;
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
        if(xhrErrorCount>10){
            clearInterval(intervalExec);
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
    for(var aNode in data){
        if(!aNode.match(/cic\-/i))
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
            var numAppWithCalls = 0;
            var appsContainer = createDOMElement('div', '', 'eaCEEGUI-raNode-raAppsContainer', nodes[i].id+'-appsContainer');
            for(var anApp in data[nodes[i].id]['applications']){
                if(appViewConfig[anApp]['visibility'] && appViewConfig[anApp]['isDemoCase']){
                    var cssClassToAdd = appViewConfig[anApp]['isDemoCase'] ? 'eaCEEGUI-raNode-raApp-innerContainerDemoCase' : 'eaCEEGUI-raNode-raApp-innerContainer';
                    //Node has call information, adding load-bar
                    if(data[nodes[i].id]['applications'][anApp]['calls']!=undefined){
                        numAppWithCalls++;
                        var aVm =  createDOMElement(
                            'div', 
                            '<p>'+anApp+'</p>', 
                            cssClassToAdd, 
                            anApp+'-'+nodes[i].id);
                        var vmInnerElements = createDOMElement(
                            'span',
                            'calls : '+data[nodes[i].id]['applications'][anApp]['calls'],
                            'eaCEEGUI-raNode-raApp-innerContainer-callSpaces',
                            'callSpace-'+numAppWithCalls+'-'+anApp+'-'+nodes[i].id);
                        var loadBar = createDOMElement(
                            'div',
                            '<div class="ebBgColor_purple" style="height: '+ data[nodes[i].id]['applications'][anApp]['calls']*100/loadBarRefNum +'%; border-radius: 5px 5px 0px 0px;">',
                            'ebBgColor_purple_40 eaCEEGUI-raNode-raAppsContainer-loadBar',
                            'load-bar-'+i+'-'+numAppWithCalls);
                        aVm.appendChild(vmInnerElements);
                        createDOMElementAndAdd('div', aVm, '', 'clearfix','');
                        aVm.appendChild(loadBar);
                    }else{                        
                        var aVm = createDOMElement(
                            'div', 
                            '<p>'+anApp+'</p>', 
                            cssClassToAdd, 
                            anApp+'-'+nodes[i].id);

                    }                    
                    createDOMElementAndAdd('div', aVm, '', 'clearfix','');
                    appsContainer.appendChild(aVm);
                }
                if(cssClassToAdd=='eaCEEGUI-raNode-raApp-innerContainerDemoCase'){
                    var rebootButton = createDOMElement(
                        'div',
                        'reboot',
                        'eaCEEGUI-raNode-raAppsContainer-rebootButton ebBtn_color_paleBlue',
                        'rebootButton--'+nodes[i].id);                    
                }
            }
        if(appsContainer.childNodes.length>0){
            rebootButton.onclick = rebootAction
            appsContainer.appendChild(rebootButton);            
        }
        nodes[i].appendChild(appsContainer);
        }
        nodesContainer.appendChild(nodes[i]);
        //setDemoCases();
        setVmHeights(4.9); 
    }
   setNodeWidth(nodes.length, 80);
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
            var padding = domNodeHeight/(2*apps[i].parentNode.childNodes.length);
            apps[i].style.paddingTop = padding +'px';
            apps[i].style.paddingBottom = padding+'px';
        }
    }
    var apps = document.getElementsByClassName('eaCEEGUI-raNode-raApp-innerContainer');
    fixPadding(apps);
    apps = document.getElementsByClassName('eaCEEGUI-raNode-raApp-innerContainerDemoCase');
    fixPadding(apps);
}

function setVmHeights(offset){
    var allNodes = document.getElementsByClassName('eaCEEGUI-raNode-raAppsContainer');
    for(var i=0; i<allNodes.length; i++){
        var vms = allNodes[i].getElementsByClassName('eaCEEGUI-raNode-raApp-innerContainerDemoCase');
        for(var j=0; j<vms.length; j++){
            vms[j].style.height = (100-offset*vms.length)/vms.length + '%';
        }
    }
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
    loopAndSet(document.getElementsByClassName('eaCEEGUI-raNode-raAppsContainer-rebootButton'), newWidth-20);
}

function showInEvent(){
    var eventDom = createDOMElement('p', latestEventString, '', '');
    var eventsPanel = document.getElementById('events_list');
    //document.getElementById('events_panel').appendChild(eventDom);
    //eventsPanel.insertBefore(eventDom, eventsPanel.childNodes.length>1?eventsPanel.childNodes[2]);
    eventsPanel.insertBefore(eventDom, eventsPanel.firstChild);
}

function rebootAction(){
    var nodeToReboot = this.id.split('rebootButton--')[1];
    latestEventString = "Rebooting "+nodeToReboot.split('\.domain')[0];
    getAndExecute(parsedConfig.ajaxlink+'/reboot--'+nodeToReboot, showInEvent);
}


function scaleOut(){
    latestEventString = 'scaling out';
    getAndExecute(parsedConfig.ajaxlink+'/actionScaleOut', showInEvent);    
}

function scaleIn(){
    latestEventString = 'scaling in';
    getAndExecute(parsedConfig.ajaxlink+'/actionScaleIn', showInEvent);
}
