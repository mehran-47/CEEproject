"use strict"

var parsedConfig = null;
var ajaxLink = "";
var frameCount = 0;

window.onload = function(){
	getAndExecute("gui_config.json", setLinkAndParseHTML);
}

/////////////////////////Configuration functions//////////////////////////////////////////

function setLinkAndParseHTML(text, parserFunction){
	parsedConfig = JSON.parse(text);
	ajaxLink = parsedConfig.ajaxlink;
	getAndExecuteWrapper();
	var intervalExec = setInterval(getAndExecuteWrapper, 3000);
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
	frameCount += 1;
}

/////////////////////////DOM functions///////////////////////////////////////////////////

function JSONToHTML(text){
	try{
		var data = JSON.parse(text);
	}catch(err){
		var data = {};
		if(window.console && window.console.log){
			console.log(err.description);
		}
	}
	var nodes = [];
	for(var aNode in data){
		if(aNode.match(/cic\-/i))
			nodes.unshift(createDOMElement('div', '<h3>'+aNode+'</h3>', 'eaCEEGUI-raNode eaCEEGUI-raNode-cic ebBgColor_darkBlue', aNode));
		else
			nodes.push(createDOMElement('div', '<h3>'+aNode+'</h3>', 'eaCEEGUI-raNode', aNode));	
	}
	var nodesContainer = document.getElementById('contentHolder');
	nodesContainer.innerHTML = '';
	//objectToDivs(nodesContainer, data);
	var detailsHTML = "";
	for(var i=0; i<nodes.length; i++){
		detailsHTML = '<div><p><span>State : </span>'+data[nodes[i].id]['state'] +'</p></div>'+
					  '<div><p><span>Status : </span>'+data[nodes[i].id]['isEnabled'] +'</p></div>';
					  //'<div><p><span>Updated at : </span>'+data[nodes[i].id]['updatedAt'] +'</p></div>';
		if(!nodes[i].id.match(/cic\-/i)){
			if(data[nodes[i].id]['state']=='up'){
				nodes[i].className += ' ebBgColor_darkBlue_80';
			}else{
				nodes[i].className += ' ebBgColor_grey_80';
			}
			if(data[nodes[i].id]['isEnabled']=='enabled'){
				nodes[i].getElementsByTagName('h3')[0].className += ' ebBgColor_darkBlue_80';
			}else{
				nodes[i].getElementsByTagName('h3')[0].className += ' ebBgColor_grey_80';
			}
		}		
		if('applications' in data[nodes[i].id]){
			for(var anApp in data[nodes[i].id]['applications']){
				createDOMElementAndAdd('div', nodes[i] , data[nodes[i].id]['applications'][anApp], 'eaCEEGUI-raNode-raApp', data[nodes[i].id]['applications'][anApp]+'-'+nodes[i].id);
			}
		}
		nodesContainer.appendChild(nodes[i]);
	}
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