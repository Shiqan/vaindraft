//
// Copyright 2018 Shiqan
//
$(document).ready(function() {
    $("#switchTheme").on('click', function() {
        switchTheme();
    });

    $("#startDraft").on('click', function() {
        getDraftStatus();
    });

    $('#overrideHeroes').change(function() {
      $("#overrideHeroesField").toggle();
    });
    
    $('#customBackground').change(function() {
      $("#customBackgroundField").toggle();
    });

    $(".hero-select").on("click", function() {
      if ($(this).hasClass("hero-highlight")) {
        newMessage($(this).data('hero'));
      } else {
        $(this).addClass("hero-highlight");
      }
      return false;
    });

    if (typeof hash != 'undefined') {
      updater.start();
    }

    new ClipboardJS('.clipboard');
});

function switchTheme() {
  var url =  location.protocol + "//" + location.host + "/theme";
  axios.get(url)
    .then(function (response) {
      location.reload();
    })
    .catch(function (error) {
      return error;
    });
}

function getDraftStatus() {
    var url =  location.protocol + "//" + location.host + "/draftstatus/" + room;
    axios.get(url)
      .then(function (response) {
        if (response.data.ready) {
          window.location = admin_url;
        } else {
          toastr.options = {"positionClass": "toast-top-center"};
          toastr.error('Not all the teams are joined yet!');
        }
      })
      .catch(function (error) {
        return error;
      });
}

function newMessage(message) {
  updater.socket.send(message);
}

var updater = {
    socket: null,

    start: function() {
        var protocol = "ws://";
        if (location.protocol == 'https:') {
            protocol = "wss://";
        }
        var url =  protocol + location.host + "/chatsocket/" + hash;
        updater.socket = new WebSocket(url);
        updater.socket.onmessage = function(event) {
            updater.showMessage(JSON.parse(event.data));
        }
    },

    showMessage: function(message) {
        if (message.type == "update") {
          updateDraft(message.message, message.index);
          updateTurnIndicator(message.index);
        }
        else if (message.type == "time") {
          $("#timer").text(message.message);
        }
        else if (message.type == "bonustime") {
          $("#bonustimer-"+message.team).text(message.message);
        }
        else if (message.type == "message") {
          toastr.options = {"positionClass": "toast-top-center"};
          toastr.error(message.message);
          removeHeroHighlight();
        }
        else if (message.type == "start") {
          toastr.options = {"positionClass": "toast-top-center"};
          toastr.success(message.message);
          turnIndicator(1);
        }
        else if (message.type == "history") {
          updateHistory(message.message);
        }
    }
};

function removeTurnIndicator() {
  $(".draft-item").removeClass('turn-indicator');
}

function turnIndicator(index) {
  $(".draft-item[data-order='"+index+"']").addClass('turn-indicator');
}

function lockHero(hero) {
  $(hero).removeClass("hero-select hero-highlight").addClass("hero-locked").off("click");
}

function removeHeroHighlight() {
  $(".hero-select").removeClass("hero-highlight");
}

function updateDraft(hero, index) {
    var draft_item = $(".draft-item > img[data-order='"+index+"']");
    var hero_select = $(".hero-select[data-hero='"+hero+"']");
    var hero_img = hero_select.attr('src');

    $(draft_item).attr('src', hero_img);
    lockHero(hero_select);
}

function updateTurnIndicator(index) {
  removeTurnIndicator();
  turnIndicator(index+1);
}

function updateHistory(draftHistory) {
    for (let i of draftHistory) {
        updateDraft(i.message, i.index);
    }
}
