define([
    'netmap/collections',
    'libs-amd/text!resources/netmap/node_info_modal.html',
    'libs-amd/text!resources/netmap/link_info_modal.html',
    'libs-amd/text!resources/netmap/vlan_info_modal.html',
    'libs/handlebars',
    'libs/backbone',
    'libs/jquery-ui-1.8.21.custom.min'
], function (Collections, NodeTemplate, LinkTemplate, VlanTemplate) {

    Handlebars.registerHelper('lowercase', function (type) {
        if (typeof type === 'string' || type instanceof String) {
            return type.toLowerCase();
        } else {
            return type;
        }
    });

    var nodeTemplate = Handlebars.compile(NodeTemplate);
    var linkTemplate = Handlebars.compile(LinkTemplate);
    var vlanTemplate = Handlebars.compile(VlanTemplate);

    return Backbone.View.extend({

        el: '#graph-info-modal',

        initialize: function () {

            this.$el.dialog({
                position: {
                    my: 'left top',
                    at: 'left top',
                    of: this.options.parent
                },
                autoOpen: false,
                resizable: false,
                width: 'auto'
            });
        },

        render: function () {

            this.$el.html(this.template(this.model));

            if (!this.$el.dialog('isOpen')) {
                this.$el.dialog('open');
            }
        },

        setModel: function (model) {

            var title;

            if (model.sysname) { // E.g. model is a node

                this.template = nodeTemplate;
                model.img = window.netmapData.staticURL +
                    model.category.toLowerCase() + '.png';
                title = model.sysname;

            } else if (_.isArray(model.edges)) { // Model is a layer2 link

                this.template = linkTemplate;
                model.sourceImg = window.netmapData.staticURL +
                    model.source.category.toLowerCase() + '.png';
                model.targetImg = window.netmapData.staticURL +
                    model.target.category.toLowerCase() + '.png';
                title = 'Link';

            } else { // Model is a layer3 link

                this.template = vlanTemplate;
                model.sourceImg = window.netmapData.staticURL +
                    model.source.category.toLowerCase() + '.png';
                model.targetImg = window.netmapData.staticURL +
                    model.target.category.toLowerCase() + '.png';

                title = 'Vlan';
            }

            this.model = model;

            this.$el.dialog('option', 'title', title);
        }

    });
});