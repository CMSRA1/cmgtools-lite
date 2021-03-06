from PhysicsTools.HeppyCore.utils.deltar import deltaR

from PhysicsTools.Heppy.analyzers.core.AutoHandle import AutoHandle
from PhysicsTools.Heppy.physicsobjects.PhysicsObjects import Tau, Muon
from PhysicsTools.Heppy.physicsobjects.Electron import Electron

from CMGTools.H2TauTau.proto.analyzers.DiLeptonAnalyzer import DiLeptonAnalyzer
from CMGTools.H2TauTau.proto.physicsobjects.DiObject import TauTau, DirectDiTau


class TauTauAnalyzer(DiLeptonAnalyzer):

    DiObjectClass = TauTau
    LeptonClass = Electron
    OtherLeptonClass = Muon

    def declareHandles(self):
        super(TauTauAnalyzer, self).declareHandles()
        if hasattr(self.cfg_ana, 'from_single_objects') and self.cfg_ana.from_single_objects:
            self.handles['taus'] = AutoHandle('slimmedTaus', 'std::vector<pat::Tau>')
        else:
            self.handles['diLeptons'] = AutoHandle('cmgDiTauCorSVFitFullSel', 'std::vector<pat::CompositeCandidate>')

        self.handles['leptons'] = AutoHandle(
            'slimmedElectrons', 
            'std::vector<pat::Electron>'
        )
        
        self.handles['otherLeptons'] = AutoHandle(
            'slimmedMuons', 
            'std::vector<pat::Muon>'
        )
        
        self.handles['jets'] = AutoHandle(
            'slimmedJets', 
            'std::vector<pat::Jet>'
        )

        self.handles['puppiMET'] = AutoHandle(
            'slimmedMETsPuppi',
            'std::vector<pat::MET>'
        )

        self.handles['pfMET'] = AutoHandle(
            'slimmedMETs',
            'std::vector<pat::MET>'
        )

        self.handles['l1IsoTau'] = AutoHandle( 
            ('l1extraParticles', 'IsoTau'), 
            'std::vector<l1extra::L1JetParticle>'   
        )


    def process(self, event):

        # method inherited from parent class DiLeptonAnalyzer
        # asks for at least on di-tau pair
        # applies the third lepton veto
        # tests leg1 and leg2
        # cleans by dR the two signal leptons
        # applies the trigger matching to the two signal leptons
        # choses the best di-tau pair, with the bestDiLepton method
        # as implemented here

        result = super(TauTauAnalyzer, self).process(event)

        event.isSignal = False
        if result:
            event.isSignal = True
        # trying to get a dilepton from the control region.
        # it must have well id'ed and trig matched legs,
        # di-lepton and tri-lepton veto must pass
        result = self.selectionSequence(event,
                                        fillCounter=True,
                                        leg1IsoCut=self.cfg_ana.looseiso1,
                                        leg2IsoCut=self.cfg_ana.looseiso2)

        if result is False:
            # really no way to find a suitable di-lepton,
            # even in the control region
            return False
        
        if not (hasattr(event, 'leg1') and hasattr(event, 'leg2')):
            return False

#     # RIC: agreed to sort by isolation 19/8/2015
#     # make sure that the legs are sorted by pt
#     if event.leg1.pt() < event.leg2.pt() :
#       event.leg1 = event.diLepton.leg2()
#       event.leg2 = event.diLepton.leg1()
#       event.selectedLeptons = [event.leg2, event.leg1]

        # RIC: agreed with Adinda to sort taus by isolation
        # JAN: This code however doesn't fix the order in the dilepton object -
        #      added it there
        # iso = self.cfg_ana.isolation
        # if event.leg1.tauID(iso) < event.leg2.tauID(iso):
        #     event.leg1 = event.diLepton.leg2()
        #     event.leg2 = event.diLepton.leg1()
        #     event.selectedLeptons = [event.leg2, event.leg1]

        event.pfmet = self.handles['pfMET'].product()[0]
        event.puppimet = self.handles['puppiMET'].product()[0]

        return True

    def buildDiLeptons(self, cmgDiLeptons, event):
        '''Build di-leptons, associate best vertex to both legs.'''
        diLeptons = []
        for index, dil in enumerate(cmgDiLeptons):
            pydil = TauTau(dil, iso=self.cfg_ana.isolation)
            pydil.leg1().associatedVertex = event.goodVertices[0]
            pydil.leg2().associatedVertex = event.goodVertices[0]
            diLeptons.append(pydil)
            pydil.mvaMetSig = pydil.met().getSignificanceMatrix()
        return diLeptons

    def buildDiLeptonsSingle(self, leptons, event):
        '''
        '''
        # RIC: patch to adapt it to the di-tau case. Need to talk to Jan
        di_objects = []
        taus = self.handles['taus'].product()
        met = self.handles['pfMET'].product()[0]
        for leg1 in taus:
            for leg2 in taus:
                if leg1 != leg2:
                    di_tau = DirectDiTau(Tau(leg1), Tau(leg2), met)
                    di_tau.leg2().associatedVertex = event.goodVertices[0]
                    di_tau.leg1().associatedVertex = event.goodVertices[0]
                    di_tau.mvaMetSig = None
                    di_objects.append(di_tau)
        return di_objects

    def buildOtherLeptons(self, cmgLeptons, event):
        '''Build muons for veto, associate best vertex, select loose ID muons.
        The loose ID selection is done to ensure that the muon has an inner track.'''
        leptons = []
        for index, lep in enumerate(cmgLeptons):
            pyl = Muon(lep)
            pyl.associatedVertex = event.goodVertices[0]
            if not pyl.muonID('POG_ID_Medium'):
                continue
            if not pyl.relIsoR(R=0.3, dBetaFactor=0.5, allCharged=0) < 0.3:
                continue
            if not self.testLegKine(pyl, ptcut=10, etacut=2.4):
                continue
            leptons.append(pyl)
        return leptons

    def buildLeptons(self, cmgOtherLeptons, event):
        '''Build electrons for third lepton veto, associate best vertex.'''
        otherLeptons = []
        for index, lep in enumerate(cmgOtherLeptons):
            pyl = Electron(lep)
            pyl.associatedVertex = event.goodVertices[0]
            pyl.rho = event.rho
            pyl.event = event
            if not pyl.mvaIDRun2('NonTrigSpring15MiniAOD', 'POG90'):
                continue
            if not pyl.relIsoR(R=0.3, dBetaFactor=0.5, allCharged=0) < 0.3:
                continue
            if not self.testLegKine(pyl, ptcut=10, etacut=2.5):
                continue
            otherLeptons.append(pyl)
        return otherLeptons

    def testLeg(self, leg, leg_pt, leg_eta, iso, isocut):
        '''requires loose isolation, pt, eta and minimal tauID cuts'''
        # RIC: relaxed
        return (abs(leg.charge()) == 1 and  # RIC: ensure that taus have abs(charge) == 1
                self.testTauVertex(leg) and
                leg.tauID(iso) < isocut and
                leg.pt() > leg_pt and
                abs(leg.eta()) < leg_eta and
                leg.tauID('decayModeFinding') > 0.5)

    def testLeg1(self, leg, isocut):
        leg_pt = self.cfg_ana.pt1
        leg_eta = self.cfg_ana.eta1
        iso = self.cfg_ana.isolation
        return self.testLeg(leg, leg_pt, leg_eta, iso, isocut)

    def testLeg2(self, leg, isocut):
        leg_pt = self.cfg_ana.pt2
        leg_eta = self.cfg_ana.eta2
        iso = self.cfg_ana.isolation
        return self.testLeg(leg, leg_pt, leg_eta, iso, isocut)

    def testTauVertex(self, tau):
        '''Tests vertex constraints, for tau'''
        # Just checks if the primary vertex the tau was reconstructed with
        # corresponds to the one used in the analysis
        # isPV = abs(tau.vertex().z() - tau.associatedVertex.z()) < 0.2
        isPV = abs(tau.leadChargedHadrCand().dz()) < 0.2
        return isPV

    def testVertex(self, lepton, dxy=0.045, dz=0.2):
        '''Tests vertex constraints, for mu, e and tau'''
        return abs(lepton.dxy()) < dxy and \
            abs(lepton.dz()) < dz

    def otherLeptonVeto(self, electrons, muons, isocut=None):
        '''Second electron veto '''
        return len(electrons) == 0

    def thirdLeptonVeto(self, electrons, muons, isocut=None):
        '''Second muon veto'''
        return len(muons) == 0

    def trigMatched(self, event, diL, requireAllMatched=False):
        matched = super(TauTauAnalyzer, self).trigMatched(event, diL, requireAllMatched=requireAllMatched, checkBothLegs=True)

        if not self.l1Matched(event, diL):
            matched = False

        return matched

    def l1Matched(self, event, diL):
        '''Additional L1 matching for 2015 trigger bug.'''
        allMatched = True

        l1objs = self.handles['l1IsoTau'].product()

        for leg in [diL.leg1(), diL.leg2()]:
            legMatched = False
            bestDR = 0.5
            for l1 in l1objs:
                if l1.pt() < 28.:
                    continue
                dR = deltaR(l1.eta(), l1.phi(), leg.eta(), leg.phi())
                if dR < bestDR:
                    legMatched = True
                    bestDR = dR
                    leg.L1 = l1
            if not legMatched:
                allMatched = False
                break

        if allMatched and diL.leg1().L1 == diL.leg2().L1:
            allMatched = False

        return allMatched

    def bestDiLepton(self, diLeptons):
        '''Returns the best diLepton (1st precedence most isolated opposite-sign,
        2nd precedence most isolated).'''
        # osDiLeptons = [dl for dl in diLeptons if dl.leg1().charge() != dl.leg2().charge()]
        # least_iso_highest_pt = lambda dl : min((dl.leg1().tauID(self.cfg_ana.isolation), -dl.leg1().pt()), (dl.leg2().tauID(self.cfg_ana.isolation), -dl.leg2().pt()))
        least_iso_highest_pt = lambda dl: (-dl.leg1().tauID(self.cfg_ana.isolation), -dl.leg1().pt(), -dl.leg2().tauID(self.cfg_ana.isolation), -dl.leg2().pt())
        # set reverse = True in case the isolation changes to MVA
        # in that case the least isolated is the one with the lowest MVAscore
        # if osDiLeptons : return sorted(osDiLeptons, key=lambda dl : least_iso(dl), reverse=False)[0]
        # else           :
        return sorted(diLeptons, key=lambda dl: least_iso_highest_pt(dl), reverse=False)[0]
