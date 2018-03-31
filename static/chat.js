//
// Copyright 2018 Shiqan
//
$(document).ready(function() {
    $(".hero-select").on("click", function() {
      if ($(this).hasClass("hero-highlight")) {
        newMessage($(this).data('hero'));
      } else {
        $(this).addClass("hero-highlight");
      }

      return false;
    })

    updater.start();
});

function newMessage(message) {
  updater.socket.send(message);
}

var updater = {
    socket: null,

    start: function() {
        // TODO get websocket url from backend
        var url = "ws://" + location.host + "/chatsocket/" + hash;
        updater.socket = new WebSocket(url);
        updater.socket.onmessage = function(event) {
            updater.showMessage(JSON.parse(event.data));
        }
    },

    showMessage: function(message) {
        if (message.type == "message") {
            // TODO toaster
            removeHeroHighlight();
        }

        else if (message.type == "update") {
            updateDraft(message.message, message.index);
        }

        else if (message.type == "history") {
            updateHistory(message.message);
        }
    }
};


function lockHero(hero) {
  $(hero).removeClass("hero-select hero-highlight").addClass("hero-locked").off("click");
}

function removeHeroHighlight() {
  $(".hero-select").removeClass("hero-highlight");
}

function updateDraft(hero, index) {
    var draft_item = $(".draft-item > img[data-order='"+index+"']");
    var hero_select = $(".hero-select[data-hero='"+hero+"']");

    $(draft_item).attr('src', '/static/images/heroes/'+hero+'.png');
    lockHero(hero_select);
}

function updateHistory(draftHistory) {
    for (let i of draftHistory) {
        updateDraft(i.message, i.index);
    }
}
