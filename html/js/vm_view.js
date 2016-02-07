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
var loadBarRefNum = 200;
var intervalExec;
var eventsDisplayExec;
var latestEventString = "";
var nodesWidthOffset = 80;
var vmsHeightOffset = 4.75;
var failureMesurerClock = new StopWatch(true, new Date());
var scalingMesurerClock = new StopWatch(true, new Date());
var evacuationMesurerClock = new StopWatch(true, new Date());

window.onload = function(){
    getAndExecute("gui_config.json", setLinkAndParseHTML);    
}

/////////////////////////Configuration functions//////////////////////////////////////////

function setLinkAndParseHTML(text, parserFunction){
    parsedConfig = JSON.parse(text);
    ajaxLink = parsedConfig.ajaxlink;
    loadBarRefNum = parsedConfig.maxcalls;
    getAndExecute('appViewConfig.json', loadViewSpecs);
    getAndExecuteWrapper();
    intervalExec = setInterval(getAndExecuteWrapper, parsedConfig.refreshinterval*1000);
    eventsDisplayExec = setInterval(checkAndDisplayEvents, parsedConfig.refreshinterval*1000);
    document.getElementById('scale_out').onclick = scaleOut;
    document.getElementById('scale_in').onclick = scaleIn;
    document.getElementById('referenceNumber').onblur = setCallReferenceNumber;
}

function loadViewSpecs(text){
    appViewConfig = JSON.parse(text); 
}

function displayTimerOnEvent(eventText){
    var clockTrigger = JSON.parse(eventText.split('#')[1]);
    var timerDOM = document.getElementById('timers');
    var activateClock = function(theClock, startStop){
        if(startStop=="start"){
            theClock.initTime = new Date();
            theClock.runClock = true;
            theClock.intervalExec = setInterval(function(){theClock.run()}, 1000);
        }else{
            theClock.runClock = false;
            clearInterval(theClock.intervalExec);
        }
    }
    if(clockTrigger.failure!=undefined){
        failureMesurerClock.titleDOM.innerHTML = "Time since failure detection:";
        timerDOM.appendChild(failureMesurerClock.titleDOM);
        timerDOM.appendChild(failureMesurerClock.DOM);        
        activateClock(failureMesurerClock, clockTrigger.failure);
    }
    if(clockTrigger.scaling!=undefined){
        scalingMesurerClock.titleDOM.innerHTML = "Time since scaling event started: ";
        timerDOM.appendChild(scalingMesurerClock.titleDOM);
        timerDOM.appendChild(scalingMesurerClock.DOM);
        activateClock(scalingMesurerClock, clockTrigger.scaling);   
    }
    if(clockTrigger.evacuation!=undefined){
        evacuationMesurerClock.titleDOM.innerHTML = "Time since evacuation started : "
        timerDOM.appendChild(evacuationMesurerClock.titleDOM);
        timerDOM.appendChild(evacuationMesurerClock.DOM);
        activateClock(evacuationMesurerClock, clockTrigger.evacuation);      
    }
}

function checkAndDisplayEvents(){
    var setLatestEvent = function(eventTextFromServer){
        console.log("Event received:"+eventTextFromServer);
        var parsedEvents = JSON.parse(eventTextFromServer);
        for(var i=0;i<parsedEvents.length; i++){
            displayTimerOnEvent(parsedEvents[i])
            latestEventString = parsedEvents[i].split('#')[0];
            showInEvent();
        }
    }
    getAndExecute(ajaxLink+'/frontEndEventStack', setLatestEvent);    
    //http://142.133.117.154:8080/frontEndEventStack
    //getAndExecute('http://142.133.117.154:8080/frontEndEventStack', setLatestEvent);
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
    getAndExecute(ajaxLink+'/getOverviewData', JSONToHTML);
    frameCount++;
}

/////////////////////////DOM functions///////////////////////////////////////////////////

function JSONToHTML(text){
    try{
        data = JSON.parse(text);
    }catch(err){
        data = {};
        xhrErrorCount++;
        if(xhrErrorCount>0){
            clearInterval(intervalExec);
            clearInterval(eventsDisplayExec);
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
                nodes[i].className += ' ebBgColor_grey_60 node_down';
            }
            if(data[nodes[i].id]['isEnabled']=='enabled'){
                nodes[i].getElementsByTagName('h3')[0].className += ' ebBgColor_darkBlue_80';
            }else{
                nodes[i].getElementsByTagName('h3')[0].className += ' ebBgColor_grey_60';
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
                            '<div class="ebBgColor_darkGreen" style="height: '+ data[nodes[i].id]['applications'][anApp]['calls']*100/loadBarRefNum +'%; border-radius: 5px 5px 0px 0px;">',
                            'ebBgColor_darkGreen_40 eaCEEGUI-raNode-raAppsContainer-loadBar',
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
        setVmHeights(vmsHeightOffset); 
    }
   setNodeWidth(nodes.length, nodesWidthOffset);
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
            var loadBars = vms[j].getElementsByClassName('eaCEEGUI-raNode-raAppsContainer-loadBar')
            for(var k=0; k<loadBars.length; k++){
                loadBars[k].style.height = 92-13*(vms.length-1) + '%';
            }
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
    var dt = new Date();
    var eventDom = createDOMElement('p', dt.toLocaleDateString() +" "+ dt.toLocaleTimeString() +": " + latestEventString, '', '');
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

function setCallReferenceNumber(){
    loadBarRefNum=document.getElementById('referenceNumber').value;
}

function dropCurtain(){
    var curtain = createDOMElement('div', '', 'eaCEEGUI-rCurtain', 'errorCurtain');
    document.body.insertBefore(curtain, document.body.childNodes[0]);
}

/////////////////////////Stopwatch object////////////////////////////////////////////////
function StopWatch(runClock, initTime){
    this.runClock = runClock;
    this.initTime = initTime;
    this.latestTime = new Date();
    this.titleDOM = createDOMElement('p', '', 'clockTitle', '');
    this.DOM = createDOMElement('div', Math.round((this.initTime - this.latestTime)/1000) + ' <span>seconds</span>', 'clockDOM', '');
    this.intervalExec = null;
    this.run = function(){
        if(this.runClock){
            this.latestTime = new Date();
            this.DOM.innerHTML = Math.round((this.latestTime-this.initTime)/1000)+ ' <span>seconds</span>';
        }
    }
}
